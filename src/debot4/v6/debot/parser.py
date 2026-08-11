"""Parse the bounded DeBot official-signal response into v6 records."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from ..domain import DeBotSignal, WalletTrade
from ..identity import bsc_address, json_safe


UTC = timezone.utc
_KOL_GROUP = re.compile(r"^kol#(?P<minutes>[1-9][0-9]*)min#", re.IGNORECASE)
_KOL_ALIAS = re.compile(r"^KOL-[0-9A-Fa-f]{4}$")
_ACTION_FIELDS = {"action", "direction", "monitor_type", "side", "signal_type", "type"}


def parse_page(payload: Mapping[str, Any], fetched_at: datetime) -> tuple[DeBotSignal, ...]:
    if payload.get("code") not in {0, "0"}:
        raise ValueError("DeBot signal response was unsuccessful")
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("DeBot signal response has no data object")
    rows = data.get("results")
    meta = data.get("meta")
    if not isinstance(rows, list) or len(rows) > 32 or not isinstance(meta, Mapping):
        raise ValueError("DeBot signal response schema is invalid")
    parsed = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        signal = _signal(row, meta, fetched_at)
        if signal is not None:
            parsed.append(signal)
    return tuple(parsed)


def next_cursor(payload: Mapping[str, Any]) -> str | None:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return None
    value = data.get("next")
    text = str(value or "").strip()
    if len(text) > 2048:
        raise ValueError("DeBot cursor exceeds the limit")
    return text or None


def _signal(
    row: Mapping[str, Any], meta: Mapping[str, Any], fetched_at: datetime
) -> DeBotSignal | None:
    if str(row.get("chain") or "").lower() != "bsc":
        return None
    group = str(row.get("group_name") or "").strip()[:256]
    prefix = group.split("#", 1)[0].lower()
    if prefix not in {"kol", "smartmoney"}:
        return None
    kind = "kol" if prefix == "kol" else "smart_money"
    signal_id = str(row.get("id") or "").strip()
    if not signal_id or len(signal_id) > 128:
        return None
    try:
        token = bsc_address(row.get("token"))
        event_at = _time(row.get("create_time"))
    except ValueError:
        return None
    token_meta = _mapping_for(meta.get("tokens"), token)
    metrics = _mapping_for(meta.get("metrics"), token)
    social = _mapping_for(meta.get("social_info"), token)
    safe = _mapping_for(meta.get("safe_info"), token)
    trading = row.get("token_trading_stat")
    trading = trading if isinstance(trading, Mapping) else {}
    wallets = _wallets(row.get("wallet_stats"), token)
    qualified, reason = _kol_qualification(
        row, kind, group, event_at, fetched_at, wallets
    )
    decimals = _int(token_meta.get("decimals"))
    supply = _decimal(token_meta.get("total_supply"))
    if supply is not None and decimals is not None and decimals >= 0:
        supply /= Decimal(10) ** decimals
    pair = _address_or_none(metrics.get("pair"))
    context = {
        "profile": {
            key: json_safe(token_meta.get(key))
            for key in ("name", "symbol", "creator_address", "launchpad")
        },
        "social": json_safe(dict(social)),
        "metrics": json_safe(dict(metrics)),
    }
    return DeBotSignal(
        signal_id=signal_id,
        token_address=token,
        signal_kind=kind,
        group_name=group,
        event_at=event_at,
        available_at=fetched_at.astimezone(UTC),
        channel_id=str(row.get("channel_id") or ""),
        pair_address=pair,
        dex_name=_text(metrics.get("dex_name"), 80),
        token_name=_text(token_meta.get("name"), 160),
        token_symbol=_text(token_meta.get("symbol"), 80),
        token_decimals=decimals,
        total_supply=supply,
        created_at=_optional_time(token_meta.get("creation_timestamp")),
        provider_fdv_usd=_first_decimal(trading.get("fdv"), trading.get("mkt_cap")),
        provider_liquidity_usd=_first_decimal(
            trading.get("liquidity"), metrics.get("liquidity")
        ),
        narrative_urls=_urls(social),
        description=_text(social.get("description"), 2000),
        wallet_trades=wallets,
        kol_buy_qualified=qualified,
        kol_buy_reason=reason,
        security_hint=json_safe(safe.get("goplus") if isinstance(safe.get("goplus"), Mapping) else {}),
        raw_context=context,
    )


def _kol_qualification(
    row: Mapping[str, Any], kind: str, group: str, event_at: datetime,
    fetched_at: datetime, wallets: tuple[WalletTrade, ...],
) -> tuple[bool, str]:
    if kind != "kol":
        return False, "not_kol"
    if str(row.get("channel_id") or "") != "2":
        return False, "not_official_channel"
    match = _KOL_GROUP.match(group)
    if match is None:
        return False, "unknown_kol_group"
    if _ACTION_FIELDS.intersection(row):
        return False, "provider_action_schema_changed"
    if event_at > fetched_at:
        return False, "future_provider_event"
    if len(wallets) < 3 or any(not _KOL_ALIAS.fullmatch(item.alias) for item in wallets):
        return False, "invalid_kol_wallets"
    if len({item.alias for item in wallets}) != len(wallets):
        return False, "duplicate_kol_wallet"
    window = timedelta(minutes=int(match.group("minutes")))
    if any(item.traded_at > event_at or event_at - item.traded_at > window for item in wallets):
        return False, "wallet_trade_outside_group_window"
    return True, "provider_ui_buy_with_windowed_wallet_trades"


def _wallets(value: object, token: str) -> tuple[WalletTrade, ...]:
    if not isinstance(value, list) or len(value) > 256:
        return ()
    result = []
    for row in value:
        if not isinstance(row, Mapping) or _ACTION_FIELDS.intersection(row):
            return ()
        try:
            row_token = bsc_address(row.get("token"))
            traded_at = _time(row.get("last_trade_time"))
        except ValueError:
            return ()
        if row_token != token:
            return ()
        volume = _decimal(row.get("volume"))
        amount = _decimal(row.get("amount_origin") or row.get("amount"))
        alias = str(row.get("alias") or "").strip()
        if volume is None or amount is None or volume <= 0 or amount <= 0 or not alias:
            return ()
        wallet = _address_or_none(row.get("wallet"))
        result.append(WalletTrade(alias, wallet, traded_at, volume, amount))
    return tuple(result)


def _mapping_for(value: object, token: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    direct = value.get(token) or value.get(token.lower())
    if isinstance(direct, Mapping):
        return direct
    for key, item in value.items():
        if str(key).lower() == token and isinstance(item, Mapping):
            return item
    return {}


def _urls(value: Mapping[str, Any]) -> tuple[str, ...]:
    result = []
    for key in ("twitter", "website", "telegram", "uri"):
        url = str(value.get(key) or "").strip()
        if url.startswith(("https://", "http://")) and len(url) <= 2048:
            result.append(url)
    return tuple(dict.fromkeys(result))


def _time(value: object) -> datetime:
    number = float(value)
    if number > 10_000_000_000:
        number /= 1000
    return datetime.fromtimestamp(number, UTC)


def _optional_time(value: object) -> datetime | None:
    try:
        return _time(value)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _decimal(value: object) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() and result >= 0 else None


def _first_decimal(*values: object) -> Decimal | None:
    return next((item for item in (_decimal(value) for value in values) if item is not None), None)


def _int(value: object) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if 0 <= result <= 255 else None


def _text(value: object, limit: int) -> str | None:
    text = str(value or "").strip()
    return text[:limit] if text else None


def _address_or_none(value: object) -> str | None:
    try:
        return bsc_address(value)
    except ValueError:
        return None
