"""Deterministic semantics derived only from sealed source content and actor policy."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re

from .actors import ActorRef
from .investigation_domain import (
    EndorsementScope,
    NarrativeAction,
    NarrativeEventKind,
)
from .source_receipts import VerifiedSourceReceipt, verify_source_receipt


_BSC_CA = re.compile(r"(?<![0-9A-Fa-f])0x[0-9A-Fa-f]{40}(?![0-9A-Fa-f])")
_DENIALS = (
    "not associated", "not affiliated", "not endorse", "did not endorse",
    "never endorsed", "fake token", "scam token", "不是官方", "没有关系",
    "与我无关", "不背书", "未背书", "否认", "假的代币", "骗局",
)
_LAUNCH = ("launch", "launched", "introducing", "推出", "发布", "上线")
_RELEASE = ("release", "released", "开源", "正式发布")
_ANNOUNCE = ("announce", "official", "正式", "宣布")
_POSITIVE = ("love", "great", "amazing", "welcome", "支持", "喜欢", "欢迎")


@dataclass(frozen=True, slots=True)
class DerivedEventSemantics:
    event_id: str
    kind: NarrativeEventKind
    action: NarrativeAction
    endorsement: EndorsementScope
    claim: str
    token_address: str = ""
    exact_ca: bool = False


def derive_event_semantics(
    actor: ActorRef,
    receipt: VerifiedSourceReceipt,
    narrative_key: str,
) -> tuple[DerivedEventSemantics, ...]:
    """Fail closed when the claimed narrative is absent from verified text."""

    if not verify_source_receipt(receipt):
        return ()
    key = narrative_key.strip()
    content = receipt._content
    if not _mentions(content, key):
        return ()
    lowered = content.casefold()
    addresses = tuple(dict.fromkeys(
        match.group(0).lower() for match in _BSC_CA.finditer(content)
    ))
    if any(term in lowered for term in _DENIALS):
        targets = addresses or ("",)
        return tuple(
            _spec(
                receipt, key, NarrativeEventKind.COUNTER_EVIDENCE,
                NarrativeAction.DENY, EndorsementScope.NEGATIVE, address,
            )
            for address in targets
        )
    output: list[DerivedEventSemantics] = []
    action = _primary_action(lowered)
    endorsement = (
        EndorsementScope.NARRATIVE_POSITIVE
        if any(term in lowered for term in _POSITIVE)
        else EndorsementScope.NARRATIVE_NEUTRAL
    )
    if actor.can_establish_origin:
        output.append(_spec(
            receipt, key, NarrativeEventKind.SOURCE_EVENT,
            action, endorsement,
        ))
    if actor.can_create_catalyst:
        output.append(_spec(
            receipt, key, NarrativeEventKind.CURRENT_CATALYST,
            action, endorsement,
        ))
    if actor.can_propagate:
        output.append(_spec(
            receipt, key, NarrativeEventKind.PROPAGATION,
            NarrativeAction.REPORT, endorsement,
        ))
    if actor.can_bind_token:
        output.extend(
            _spec(
                receipt, key, NarrativeEventKind.TOKEN_BINDING,
                NarrativeAction.EXACT_CA_CLAIM,
                EndorsementScope.TOKEN_EXPLICIT, address,
            )
            for address in addresses
        )
    return tuple(output)


def _spec(
    receipt: VerifiedSourceReceipt,
    key: str,
    kind: NarrativeEventKind,
    action: NarrativeAction,
    endorsement: EndorsementScope,
    address: str = "",
) -> DerivedEventSemantics:
    identity = "|".join((receipt.source_id, key.casefold(), kind.value, address))
    event_id = (
        f"{receipt.provider.value}:"
        f"{sha256(identity.encode()).hexdigest()[:24]}"
    )
    target = f" exact CA {address}" if address else ""
    claim = f"verified @{receipt.author_handle} {kind.value} for {key}{target}"
    return DerivedEventSemantics(
        event_id, kind, action, endorsement, claim, address, bool(address)
    )


def _primary_action(text: str) -> NarrativeAction:
    if any(term in text for term in _LAUNCH):
        return NarrativeAction.LAUNCH
    if any(term in text for term in _RELEASE):
        return NarrativeAction.RELEASE
    if any(term in text for term in _ANNOUNCE):
        return NarrativeAction.ANNOUNCE
    return NarrativeAction.ORIGINATE


def _mentions(content: str, narrative_key: str) -> bool:
    needle = "".join(char for char in narrative_key.casefold() if char.isalnum())
    haystack = "".join(char for char in content.casefold() if char.isalnum())
    return len(needle) >= 2 and needle in haystack
