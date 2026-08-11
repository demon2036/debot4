"""Strict extraction of an exact X status lead from DeBot metadata."""

from __future__ import annotations

from typing import Mapping

from .domain import TokenRef
from .fxtwitter import FxTwitterError, parse_x_status_url
from .hashing import stable_identity
from .models import RESEARCH_SCHEMA, is_exact_bsc_token


def resolve_status_lead(
    token: TokenRef,
    token_context: Mapping[str, object] | object,
) -> tuple[str | None, str | None, str | None, str, str, bool]:
    """Return canonical URL, identity, reason, and integrity-error flag."""

    material: dict[str, object] = {
        "schema": RESEARCH_SCHEMA,
        "token": {"chain": token.chain, "address": token.address},
    }
    if not is_exact_bsc_token(token):
        identity, _ = stable_identity("v6-debot-x-lead", material)
        return None, None, None, identity, "unsupported_token_identity", True
    if not isinstance(token_context, Mapping):
        identity, _ = stable_identity("v6-debot-x-lead", material)
        return None, None, None, identity, "token_context_missing", False
    schema = token_context.get("schema")
    trust = token_context.get("trust")
    material.update({"context_schema": schema, "context_trust": trust})
    if schema != "debot.token_context.v1" or trust != "unverified_provider_metadata":
        identity, _ = stable_identity("v6-debot-x-lead", material)
        return None, None, None, identity, "token_context_contract_mismatch", True
    leads = token_context.get("research_leads")
    url = leads.get("twitter_url") if isinstance(leads, Mapping) else None
    material["twitter_url"] = url if isinstance(url, str) else None
    if not isinstance(url, str) or not url.strip():
        identity, _ = stable_identity("v6-debot-x-lead", material)
        return None, None, None, identity, "exact_status_lead_missing", False
    try:
        handle, status_id = parse_x_status_url(url)
    except FxTwitterError:
        identity, _ = stable_identity("v6-debot-x-lead", material)
        return None, None, None, identity, "exact_status_lead_missing", False
    canonical_url = f"https://x.com/{handle}/status/{status_id}"
    material["canonical_url"] = canonical_url
    identity, _ = stable_identity("v6-debot-x-lead", material)
    return canonical_url, handle, status_id, identity, "exact_status_lead", False
