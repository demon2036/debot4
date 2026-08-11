"""Validation for distinct historical KOL evidence contracts."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .models import (
    HistoricalKolFact,
    KOL_BUY_EVIDENCE_SCHEMA,
    KOL_PROXY_EVIDENCE_SCHEMA,
    KOL_QUALIFICATION_REASON,
)


WALLET_BUY = "windowed_wallet_buy"
PARTICIPATION_PROXY = "rank_kol_count_increase_proxy"
_KOL_GROUP = re.compile(r"^kol#(?P<minutes>[1-9][0-9]*)min#", re.IGNORECASE)
_KOL_ALIAS = re.compile(r"^KOL-[0-9A-Fa-f]{4}$")


@dataclass(frozen=True, slots=True)
class ContractAssessment:
    accepted: bool
    reason: str
    evidence_kind: str | None = None
    source_actor: str | None = None
    provider: Mapping[str, object] | None = None


def assess_contract(
    metadata: Mapping[str, object], fact: HistoricalKolFact
) -> ContractAssessment:
    schema = metadata.get("schema")
    if schema == KOL_BUY_EVIDENCE_SCHEMA:
        if metadata.get("signal_group") != "KOL":
            return ContractAssessment(False, "fact_signal_group_not_kol")
        provider = _mapping(metadata.get("provider_kol_buy_evidence"))
        if _wallet_contract_valid(provider, fact):
            return ContractAssessment(
                True, "strictly_prior_kol_wallet_buy_qualified", WALLET_BUY,
                str(provider.get("provider_group_name") or "DeBot KOL"), provider,
            )
        return ContractAssessment(
            False, "provider_kol_buy_contract_invalid", WALLET_BUY,
            str(provider.get("provider_group_name") or "DeBot KOL"), provider,
        )
    if schema == KOL_PROXY_EVIDENCE_SCHEMA:
        if metadata.get("signal_group") != "KOL_RANKS":
            return ContractAssessment(False, "fact_signal_group_not_kol_ranks")
        provider = _mapping(metadata.get("provider_kol_participation_proxy"))
        if _proxy_contract_valid(provider, fact):
            return ContractAssessment(
                True, "strictly_prior_kol_participation_proxy_qualified",
                PARTICIPATION_PROXY, "DeBot ranks", provider,
            )
        return ContractAssessment(
            False, "provider_kol_proxy_contract_invalid", PARTICIPATION_PROXY,
            "DeBot ranks", provider,
        )
    return ContractAssessment(False, "fact_metadata_schema_invalid")


def _wallet_contract_valid(
    provider: Mapping[str, object], fact: HistoricalKolFact
) -> bool:
    event_ms = int(fact.event_time.timestamp() * 1000)
    wallets = provider.get("kol_wallet_identifiers")
    count = provider.get("kol_wallet_count")
    group = provider.get("provider_group_name")
    match = _KOL_GROUP.match(group) if isinstance(group, str) else None
    if (
        provider.get("evidence_contract_version") != 1
        or provider.get("qualified") is not True
        or provider.get("is_kol_buy") is not True
        or provider.get("status") != "provider_ui_asserted"
        or provider.get("reason") != KOL_QUALIFICATION_REASON
        or provider.get("verification_level") != "provider_ui_asserted"
        or provider.get("chain_verified") is not False
        or provider.get("provider_channel_id") != "2"
        or match is None
        or provider.get("provider_event_time_ms") != event_ms
        or provider.get("buy_semantics_source")
        != "debot.v6.parser.windowed_kol_wallet_trades"
        or isinstance(count, bool)
        or not isinstance(count, int)
        or count < 3
        or not isinstance(wallets, list)
        or len(wallets) != count
    ):
        return False
    aliases: set[str] = set()
    window_ms = int(match.group("minutes")) * 60_000
    for wallet in wallets:
        if not isinstance(wallet, Mapping):
            return False
        alias = wallet.get("provider_wallet_alias")
        trade_ms = wallet.get("provider_trade_time_ms")
        if (
            not isinstance(alias, str)
            or not _KOL_ALIAS.fullmatch(alias)
            or alias in aliases
            or isinstance(trade_ms, bool)
            or not isinstance(trade_ms, int)
            or trade_ms < 0
            or trade_ms > event_ms
            or event_ms - trade_ms > window_ms
        ):
            return False
        aliases.add(alias)
    return len(aliases) >= 3


def _proxy_contract_valid(
    provider: Mapping[str, object], fact: HistoricalKolFact
) -> bool:
    previous = provider.get("previous_kol_count")
    current = provider.get("current_kol_count")
    increase = provider.get("increase")
    event_ms = int(fact.event_time.timestamp() * 1000)
    integers = (previous, current, increase)
    return bool(
        provider.get("evidence_contract_version") == 1
        and provider.get("label") == "historical_kol_participation_proxy"
        and provider.get("kind") == "debot_ranks_kol_count_increase"
        and provider.get("is_wallet_buy") is False
        and provider.get("is_kol_buy") is False
        and provider.get("verification_level") == "provider_rank_snapshot_delta"
        and provider.get("chain_verified") is False
        and provider.get("source_endpoint") == "/api/dashboard/meme/v3/ranks"
        and provider.get("first_observed_time_ms") == event_ms
        and provider.get("time_source") == "client_fetch_completion"
        and provider.get("provider_token_address") == fact.token_address
        and all(isinstance(value, int) and not isinstance(value, bool) for value in integers)
        and previous >= 0
        and increase > 0
        and current - previous == increase
    )


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}
