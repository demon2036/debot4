"""Direct public-API providers for the independent BSC gainer audit."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from debot4.v6.identity import bsc_address

from .http import DirectJsonClient
from .models import Board, Gainer, HttpAttempt


CMC_URL = "https://dapi.coinmarketcap.com/dex/v1/tokens/gainer-loser/list"
GECKO_URL = (
    "https://api.geckoterminal.com/api/v2/networks/bsc/"
    "trending_pools?page=1&include=base_token%2Cquote_token%2Cdex&duration=1h"
)


def fetch_bsc_gainers(
    client: DirectJsonClient,
    *,
    as_of_us: int,
    limit: int = 20,
    min_liquidity_usd: Decimal = Decimal("25000"),
) -> Board:
    """Fetch exact CMC 1h gainers, then a clearly labelled trending fallback."""
    if not 1 <= limit <= 100 or min_liquidity_usd < 0:
        raise ValueError("invalid DEX audit bounds")
    attempts: list[HttpAttempt] = []
    body = {
        "nextPageIndex": "",
        "sortBy": "priceChange1h",
        "sortType": "desc",
        "interval": "1h",
        "pageSize": 100,
        "platformIds": "14",
        "filter": {"minLiquidity": float(min_liquidity_usd)},
    }
    response = client.request_json(
        source="coinmarketcap_datahub", method="POST", url=CMC_URL, body=body
    )
    attempts.append(response.attempt)
    try:
        rows = _cmc_rows(response.payload, min_liquidity_usd)
    except (KeyError, TypeError, ValueError) as exc:
        rows = []
        attempts[-1] = _parse_failure(attempts[-1], exc)
    if rows:
        return Board(
            as_of_us=response.attempt.completed_at_us,
            source="coinmarketcap_datahub",
            source_url=CMC_URL,
            universe="bsc_1h_gainers_min_liquidity_25000",
            ranking_exact=True,
            rows=tuple(_top(rows, limit)),
            attempts=tuple(attempts),
        )
    fallback = client.request_json(
        source="geckoterminal", method="GET", url=GECKO_URL
    )
    attempts.append(fallback.attempt)
    try:
        rows = _gecko_rows(fallback.payload, min_liquidity_usd)
    except (KeyError, TypeError, ValueError) as exc:
        rows = []
        attempts[-1] = _parse_failure(attempts[-1], exc)
    if rows:
        return Board(
            as_of_us=fallback.attempt.completed_at_us,
            source="geckoterminal",
            source_url=GECKO_URL,
            universe="bsc_1h_trending_fallback_min_liquidity_25000",
            ranking_exact=False,
            rows=tuple(_top(rows, limit)),
            attempts=tuple(attempts),
            failure_reason="exact CMC gainer board unavailable; fallback is not global",
        )
    failures = "; ".join(
        f"{item.source}: {item.failure_reason or 'empty board'}" for item in attempts
    )
    return Board(
        as_of_us=attempts[-1].completed_at_us if attempts else as_of_us,
        source="none",
        source_url=CMC_URL,
        universe="bsc_1h_gainers_unavailable",
        ranking_exact=False,
        rows=(),
        attempts=tuple(attempts),
        failure_reason=failures,
    )


def _cmc_rows(payload: Any, minimum: Decimal) -> list[Gainer]:
    items = payload["data"]["leaderboardList"]
    if not isinstance(items, list):
        raise TypeError("CMC leaderboardList is not a list")
    rows = []
    for item in items:
        if str(item.get("pid", item.get("platformId", ""))) != "14":
            continue
        stats = item.get("sts", item.get("stats", []))
        h1 = next(
            (s for s in stats if s.get("tp", s.get("type")) == "1h"), None
        )
        change = _decimal(None if h1 is None else h1.get("pc", h1.get("priceChangeRate")))
        liquidity = _decimal(item.get("liqUsd", item.get("liquidityUsd")))
        address = _address(item.get("addr", item.get("address")))
        if change is None or liquidity is None or liquidity < minimum or not address:
            continue
        rows.append(
            Gainer(
                token_address=address,
                pair_address=None,
                symbol=str(item.get("sym", item.get("symbol", "")))[:80],
                name=str(item.get("n", item.get("name", "")))[:160],
                h1_change_pct=change,
                liquidity_usd=liquidity,
                fdv_usd=_decimal(item.get("fdv")),
                market_cap_usd=_decimal(item.get("mcap", item.get("marketCap"))),
                price_usd=_decimal(item.get("p", item.get("priceUsd"))),
                volume_h1_usd=_decimal(None if h1 is None else h1.get("vu", h1.get("volumeUsd"))),
                txns_h1=_integer(None if h1 is None else h1.get("txs", h1.get("transactions"))),
            )
        )
    return rows


def _gecko_rows(payload: Any, minimum: Decimal) -> list[Gainer]:
    included = {
        str(item.get("id")): item.get("attributes", {})
        for item in payload.get("included", [])
        if item.get("type") == "token"
    }
    rows = []
    for item in payload["data"]:
        attributes = item["attributes"]
        liquidity = _decimal(attributes.get("reserve_in_usd"))
        change = _decimal(attributes.get("price_change_percentage", {}).get("h1"))
        relation = item.get("relationships", {}).get("base_token", {}).get("data", {})
        token_id = str(relation.get("id", ""))
        token = included.get(token_id, {})
        address = _address(token.get("address") or token_id.rsplit("_", 1)[-1])
        if change is None or liquidity is None or liquidity < minimum or not address:
            continue
        transactions = attributes.get("transactions", {}).get("h1", {})
        rows.append(
            Gainer(
                token_address=address,
                pair_address=_address(item.get("id", "").rsplit("_", 1)[-1]),
                symbol=str(token.get("symbol", ""))[:80],
                name=str(token.get("name", attributes.get("name", "")))[:160],
                h1_change_pct=change,
                liquidity_usd=liquidity,
                fdv_usd=_decimal(attributes.get("fdv_usd")),
                market_cap_usd=_decimal(attributes.get("market_cap_usd")),
                price_usd=_decimal(attributes.get("base_token_price_usd")),
                volume_h1_usd=_decimal(attributes.get("volume_usd", {}).get("h1")),
                txns_h1=_sum_txns(transactions),
            )
        )
    return rows


def _top(rows: list[Gainer], limit: int) -> list[Gainer]:
    unique: dict[str, Gainer] = {}
    for row in rows:
        previous = unique.get(row.token_address)
        if previous is None or row.h1_change_pct > previous.h1_change_pct:
            unique[row.token_address] = row
    return sorted(unique.values(), key=lambda row: row.h1_change_pct, reverse=True)[:limit]


def _decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _integer(value: object) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _sum_txns(value: object) -> int | None:
    if not isinstance(value, dict):
        return None
    buys, sells = _integer(value.get("buys")), _integer(value.get("sells"))
    return None if buys is None and sells is None else (buys or 0) + (sells or 0)


def _address(value: object) -> str:
    try:
        return bsc_address(value)
    except ValueError:
        return ""


def _parse_failure(attempt: HttpAttempt, exc: Exception) -> HttpAttempt:
    return HttpAttempt(
        source=attempt.source,
        method=attempt.method,
        url=attempt.url,
        request_json=attempt.request_json,
        started_at_us=attempt.started_at_us,
        completed_at_us=attempt.completed_at_us,
        latency_ms=attempt.latency_ms,
        http_status=attempt.http_status,
        response_bytes=attempt.response_bytes,
        success=False,
        failure_reason=f"parse error: {type(exc).__name__}: {str(exc)[:120]}",
    )
