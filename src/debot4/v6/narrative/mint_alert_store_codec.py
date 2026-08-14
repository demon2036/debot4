"""SQLite encoding for accepted catalyst-to-mint alerts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json
import sqlite3

from .catalyst_mint import CatalystMintMatch
from .mint_alert import MintAlert


class MintAlertStoreError(ValueError):
    """Durable alert state is malformed or contradictory."""


def insert_values(alert: MintAlert) -> tuple[object, ...]:
    match = alert.match
    return (
        alert.alert_id,
        match.match_id,
        match.exact_ca,
        match.token_stage,
        match.match_kind,
        match.catalyst_tweet_id,
        match.catalyst_author,
        match.catalyst_text,
        match.catalyst_created_at.isoformat(),
        match.catalyst_fetched_at.isoformat(),
        match.token_created_at.isoformat(),
        match.observed_at.isoformat(),
        match.token_name,
        match.token_symbol,
        _decimal(match.provider_fdv_usd),
        match.launchpad,
        match.token_description,
        _json(match.token_social_urls),
        match.token_status_url,
        alert.raised_at.isoformat(),
        alert.raised_at.isoformat(),
    )


def alert_from_row(row: sqlite3.Row) -> MintAlert:
    try:
        if row["authorizes_trade"] != 0:
            raise ValueError
        match = CatalystMintMatch(
            exact_ca=row["exact_ca"],
            token_stage=row["token_stage"],
            token_created_at=datetime.fromisoformat(row["token_created_at"]),
            observed_at=datetime.fromisoformat(row["match_observed_at"]),
            token_name=row["token_name"],
            token_symbol=row["token_symbol"],
            provider_fdv_usd=(
                None
                if row["provider_fdv_usd"] is None
                else Decimal(row["provider_fdv_usd"])
            ),
            launchpad=row["launchpad"],
            token_description=row["token_description"],
            token_social_urls=_strings(row["token_social_urls_json"]),
            token_status_url=row["token_status_url"],
            catalyst_tweet_id=row["catalyst_tweet_id"],
            catalyst_author=row["catalyst_author"],
            catalyst_text=row["catalyst_text"],
            catalyst_created_at=datetime.fromisoformat(
                row["catalyst_created_at"]
            ),
            catalyst_fetched_at=datetime.fromisoformat(
                row["catalyst_fetched_at"]
            ),
        )
        alert = MintAlert(
            match=match,
            raised_at=datetime.fromisoformat(row["raised_at"]),
        )
        if (
            match.match_id != row["match_id"]
            or match.match_kind != row["match_kind"]
            or alert.alert_id != row["alert_id"]
        ):
            raise ValueError
        return alert
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MintAlertStoreError(str(row["alert_id"])) from exc


def _strings(value: str) -> tuple[str, ...]:
    parsed = json.loads(value)
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise ValueError("mint alert JSON list is invalid")
    return tuple(parsed)


def _json(values: tuple[str, ...]) -> str:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")
