"""SQLite row encoding and conservative enrichment for mint evidence."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
import json
import sqlite3

from ..identity import utc_datetime
from .mint_location import MintLocation


HEARTBEAT_INTERVAL = timedelta(minutes=1)


class MintLocationConflict(ValueError):
    """One source identity supplied contradictory immutable evidence."""


def insert_values(item: MintLocation) -> tuple[object, ...]:
    observed = item.observed_at.isoformat()
    return (
        item.location_id, item.exact_ca, item.source, observed, observed,
        time_text(item.created_at), item.launchpad, item.token_name,
        item.token_symbol, decimal_text(item.provider_fdv_usd),
        urls_text(item.social_urls), item.transaction_hash, item.block_number,
        item.block_hash, item.transaction_index, item.factory_address,
    )


def merge_values(
    row: sqlite3.Row, item: MintLocation,
) -> tuple[object, ...] | None:
    immutable = {
        "exact_ca": item.exact_ca,
        "source": item.source,
        "transaction_hash": item.transaction_hash,
        "block_number": item.block_number,
        "block_hash": item.block_hash,
        "transaction_index": item.transaction_index,
        "factory_address": item.factory_address,
    }
    if any(row[key] != value for key, value in immutable.items()):
        raise MintLocationConflict(item.location_id)
    created = _coalesce_consistent(
        row["created_at"], time_text(item.created_at), item.location_id
    )
    old_urls = json.loads(row["social_urls_json"])
    if not isinstance(old_urls, list) or any(
        not isinstance(value, str) for value in old_urls
    ):
        raise MintLocationConflict(item.location_id)
    urls = tuple(dict.fromkeys((*old_urls, *item.social_urls)))
    last_observed = _heartbeat(row["last_observed_at"], item.observed_at)
    values = (
        min(row["first_observed_at"], item.observed_at.isoformat()),
        last_observed,
        created,
        row["launchpad"] or item.launchpad,
        row["token_name"] or item.token_name,
        row["token_symbol"] or item.token_symbol,
        row["provider_fdv_usd"] or decimal_text(item.provider_fdv_usd),
        urls_text(urls),
    )
    current = tuple(row[key] for key in (
        "first_observed_at", "last_observed_at", "created_at", "launchpad",
        "token_name", "token_symbol", "provider_fdv_usd", "social_urls_json",
    ))
    return None if values == current else values


def location_from_row(row: sqlite3.Row) -> MintLocation:
    try:
        if row["authorizes_trade"] != 0:
            raise ValueError
        urls = json.loads(row["social_urls_json"])
        if not isinstance(urls, list) or any(
            not isinstance(value, str) for value in urls
        ):
            raise ValueError
        return MintLocation(
            exact_ca=row["exact_ca"], source=row["source"],
            observed_at=datetime.fromisoformat(row["first_observed_at"]),
            created_at=(
                None if row["created_at"] is None
                else datetime.fromisoformat(row["created_at"])
            ),
            launchpad=row["launchpad"], token_name=row["token_name"],
            token_symbol=row["token_symbol"],
            provider_fdv_usd=(
                None if row["provider_fdv_usd"] is None
                else Decimal(row["provider_fdv_usd"])
            ),
            social_urls=tuple(urls), transaction_hash=row["transaction_hash"],
            block_number=row["block_number"], block_hash=row["block_hash"],
            transaction_index=row["transaction_index"],
            factory_address=row["factory_address"],
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MintLocationConflict(str(row["location_id"])) from exc


def time_text(value: datetime | None) -> str | None:
    return None if value is None else utc_datetime(value).isoformat()


def decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def urls_text(values: tuple[str, ...]) -> str:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def _coalesce_consistent(old: object, new: object, identity: str) -> object:
    if old is not None and new is not None and old != new:
        raise MintLocationConflict(identity)
    return old if old is not None else new


def _heartbeat(old: str, observed_at: datetime) -> str:
    old_time = datetime.fromisoformat(old)
    observed = utc_datetime(observed_at)
    if observed <= old_time or observed - old_time < HEARTBEAT_INTERVAL:
        return old
    return observed.isoformat()
