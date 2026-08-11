"""Conservatively normalize formatter-only enum mistakes."""

from __future__ import annotations

import json

from .briefs import (
    CaCarrierStatus,
    CatalystType,
    EventRole,
    NarrativePhase,
    brief_payload_object,
)


_ENUM_FIELDS = {
    "event_role": EventRole,
    "phase": NarrativePhase,
    "catalyst_type": CatalystType,
    "ca_carrier_status": CaCarrierStatus,
}


def normalize_formatter_enums(text: str) -> str:
    """Map unsupported model labels to unknown without changing evidence."""

    payload = dict(brief_payload_object(text))
    for field, enum_type in _ENUM_FIELDS.items():
        value = payload.get(field, "unknown")
        try:
            enum_type(value)
        except (TypeError, ValueError):
            payload[field] = "unknown"
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
