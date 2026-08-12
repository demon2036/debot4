"""Pure records for directly disclosed links between X accounts."""

from __future__ import annotations

from dataclasses import dataclass
import re


_HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}")
_USER_ID = re.compile(r"[1-9][0-9]{5,24}")


@dataclass(frozen=True, slots=True)
class XLinkedAccountEvidence:
    source_handle: str
    source_user_id: str
    linked_handle: str | None
    linked_user_id: str | None
    relationship_claim: str
    evidence_url: str
    payload_sha256: str
    reciprocal: bool

    def __post_init__(self) -> None:
        source = self.source_handle.strip().lstrip("@")
        linked = self.linked_handle.strip().lstrip("@") if self.linked_handle else None
        if not _HANDLE.fullmatch(source) or (
            linked is not None and not _HANDLE.fullmatch(linked)
        ):
            raise ValueError("linked-account evidence needs valid X handles")
        if not _USER_ID.fullmatch(self.source_user_id):
            raise ValueError("linked-account source needs a stable X ID")
        if self.linked_user_id and (
            linked is None or not _USER_ID.fullmatch(self.linked_user_id)
        ):
            raise ValueError("linked-account target X ID is invalid")
        if not self.evidence_url.startswith("https://api.fxtwitter.com/"):
            raise ValueError("linked-account evidence must be a fetched X profile")
        if not re.fullmatch(r"[0-9a-f]{64}", self.payload_sha256):
            raise ValueError("linked-account profile fingerprint is invalid")
        if not self.relationship_claim.strip():
            raise ValueError("linked-account relationship claim is required")
        object.__setattr__(self, "source_handle", source)
        object.__setattr__(self, "linked_handle", linked)

    @property
    def target_identity_verified(self) -> bool:
        return self.linked_user_id is not None

    @property
    def named_target(self) -> bool:
        return self.linked_handle is not None
