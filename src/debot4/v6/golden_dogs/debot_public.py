"""Anonymous DeBot research adapter with bounded, receipted JSON requests."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import time
from typing import Any, Mapping
from urllib.parse import urlencode

import httpx

from .models import Candle, EvidenceReceipt, MarketTrace


BASE_URL = "https://app.debot.ai"
RANK_PATH = "/api/dashboard/meme/v4/ranks"
MARKET_PATH = "/api/market/v4"
TOKEN_INFO_PATH = "/api/market/token/info"


class PublicDeBotError(RuntimeError):
    """Sanitized public endpoint transport or schema failure."""


@dataclass(frozen=True, slots=True)
class RankPage:
    rows: tuple[Mapping[str, Any], ...]
    receipt: EvidenceReceipt


@dataclass(frozen=True, slots=True)
class TokenDetailPage:
    data: Mapping[str, Any]
    receipt: EvidenceReceipt


class PublicDeBotClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        max_response_bytes: int = 8_000_000,
        attempts: int = 3,
        client: httpx.Client | None = None,
    ) -> None:
        if timeout_seconds <= 0 or max_response_bytes <= 0 or not 1 <= attempts <= 5:
            raise ValueError("invalid public DeBot client bounds")
        self.max_bytes = max_response_bytes
        self.attempts = attempts
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=12, max_keepalive_connections=8),
            headers={
                "Accept": "application/json, text/plain, */*",
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/meme",
                "User-Agent": "Mozilla/5.0 DeBot4EvidenceResearch/1.0",
            },
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "PublicDeBotClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch_rank_page(
        self,
        chain: str,
        source: str,
        min_age_minutes: int,
        max_age_minutes: int,
        *,
        limit: int = 100,
    ) -> RankPage:
        if chain not in {"bsc", "robinhood"} or not source or not 0 <= min_age_minutes <= max_age_minutes:
            raise ValueError("invalid rank query")
        if not 1 <= limit <= 100:
            raise ValueError("rank page limit must be between 1 and 100")
        body = {
            "column": "completed",
            "limit": limit,
            "sort_field": "",
            "groups": [{
                "meme_types": [f"{chain}:{source}"],
                "filter": {"create_time_minutes": [min_age_minutes, max_age_minutes]},
            }],
        }
        request_context = json.dumps(
            body, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        payload, receipt = self._json(
            "POST", RANK_PATH, body=body, request_context=request_context,
        )
        data = _object(payload.get("data"), "rank data")
        rows = data.get("completed")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise PublicDeBotError("DeBot rank rows have invalid schema")
        return RankPage(tuple(rows), receipt)

    def fetch_market(
        self,
        chain: str,
        token: str,
        *,
        interval_seconds: int = 86_400,
        limit: int = 1_000,
        end: int = 0,
    ) -> MarketTrace:
        if chain not in {"bsc", "robinhood"} or interval_seconds <= 0:
            raise ValueError("invalid market query")
        if not 1 <= limit <= 1_000 or end < 0:
            raise ValueError("invalid market pagination")
        query = urlencode({
            "token": token,
            "chain": chain,
            "pair": "",
            "dex_name": "unknown",
            "interval": interval_seconds,
            "limit": limit,
            "end": end,
        })
        payload, receipt = self._json("GET", f"{MARKET_PATH}?{query}")
        data = _object(payload.get("data"), "market data")
        raw_bars = data.get("list")
        if raw_bars is None:
            raw_bars = []
        if not isinstance(raw_bars, list) or any(not isinstance(row, dict) for row in raw_bars):
            raise PublicDeBotError("DeBot market bars have invalid schema")
        bars = tuple(_parse_candle(row) for row in raw_bars)
        supply = _decimal(data.get("total_supply"))
        decimals = _integer(data.get("decimals"))
        normalized = None
        if supply is not None and decimals is not None:
            normalized = supply / (Decimal(10) ** decimals)
        return MarketTrace(bars, normalized, decimals, receipt)

    def fetch_token_detail(self, chain: str, token: str) -> TokenDetailPage:
        if chain not in {"bsc", "robinhood"}:
            raise ValueError("invalid token-detail chain")
        query = urlencode({"chain": chain, "token": token})
        payload, receipt = self._json("GET", f"{TOKEN_INFO_PATH}?{query}")
        data = _object(payload.get("data"), "token detail")
        _object(data.get("meta"), "token metadata")
        return TokenDetailPage(data, receipt)

    def _json(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, object] | None = None,
        request_context: str | None = None,
    ) -> tuple[dict[str, Any], EvidenceReceipt]:
        last_error: Exception | None = None
        url = f"{BASE_URL}{path}"
        for attempt in range(self.attempts):
            try:
                response = self._client.request(method, url, json=body)
                if response.status_code != 200:
                    raise PublicDeBotError(f"DeBot public API returned HTTP {response.status_code}")
                raw = response.content
                if len(raw) > self.max_bytes:
                    raise PublicDeBotError("DeBot public API response exceeded byte limit")
                payload = response.json()
                if not isinstance(payload, dict) or payload.get("code") != 0:
                    raise PublicDeBotError("DeBot public API returned an unsuccessful envelope")
                fetched_at = int(time.time())
                receipt = EvidenceReceipt(
                    kind="debot_public_json",
                    url=str(response.url),
                    fetched_at=fetched_at,
                    sha256=hashlib.sha256(raw).hexdigest(),
                    request_sha256=(
                        hashlib.sha256(request_context.encode("utf-8")).hexdigest()
                        if request_context is not None else None
                    ),
                    request_context=request_context,
                )
                return payload, receipt
            except (httpx.HTTPError, ValueError, PublicDeBotError) as exc:
                last_error = exc
                if attempt + 1 < self.attempts:
                    time.sleep(0.25 * (2**attempt))
        raise PublicDeBotError("DeBot public API request failed") from last_error


def _parse_candle(row: Mapping[str, Any]) -> Candle:
    values = [_decimal(row.get(key)) for key in ("open", "high", "low", "close", "volume")]
    if any(value is None for value in values):
        raise PublicDeBotError("DeBot market candle contains invalid numbers")
    return Candle(_integer(row.get("time")) or 0, *values)  # type: ignore[arg-type]


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PublicDeBotError(f"DeBot {label} is not an object")
    return value


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool) or str(value).strip() == "":
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise PublicDeBotError("DeBot API contains an invalid number") from exc
    return number if number.is_finite() else None


def _integer(value: object) -> int | None:
    number = _decimal(value)
    return int(number) if number is not None and number == number.to_integral() else None
