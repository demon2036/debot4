"""Sealed receipts issued only after a trusted adapter parses source bytes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import re
from secrets import token_bytes
from urllib.parse import urlsplit

from .investigation_domain import EvidenceProvider


_ID = re.compile(r"[1-9][0-9]{5,24}")
_HANDLE = re.compile(r"[A-Za-z0-9_]{1,32}")
_TELEGRAM_CHANNEL = re.compile(r"[A-Za-z0-9_]{5,32}")
_DOC_ID = re.compile(r"[A-Za-z0-9:._/@+-]{3,160}")
_SEAL_KEY = token_bytes(32)
_X_PROVIDERS = {EvidenceProvider.X_GRAPHQL, EvidenceProvider.FXTWITTER}
_DOCUMENT_PROVIDERS = {
    EvidenceProvider.OFFICIAL_HTTP,
    EvidenceProvider.OFFICIAL_REPOSITORY,
}


def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True, init=False)
class VerifiedSourceReceipt:
    provider: EvidenceProvider
    source_id: str
    canonical_url: str
    author_id: str
    author_handle: str
    published_at: datetime
    fetched_at: datetime
    content_sha256: str
    raw_payload_sha256: str
    response_identity: str
    _content: str
    _raw_payload: bytes
    _seal: str

    def __init__(self) -> None:
        raise TypeError("receipts are issued only by trusted source adapters")

    def to_payload(self) -> dict[str, str]:
        return {
            "provider": self.provider.value,
            "source_id": self.source_id,
            "canonical_url": self.canonical_url,
            "author_id": self.author_id,
            "author_handle": self.author_handle,
            "published_at": self.published_at.isoformat(),
            "fetched_at": self.fetched_at.isoformat(),
            "content_sha256": self.content_sha256,
            "raw_payload_sha256": self.raw_payload_sha256,
            "response_identity": self.response_identity,
        }


class _ReceiptIssuer:
    def x_status(
        self,
        *,
        provider: EvidenceProvider,
        status_id: str,
        author_id: str,
        author_handle: str,
        content: str,
        published_at: datetime,
        fetched_at: datetime,
        raw_payload: bytes,
        response_identity: str,
    ) -> VerifiedSourceReceipt:
        provider = EvidenceProvider(provider)
        handle = author_handle.strip().lstrip("@").casefold()
        if provider not in _X_PROVIDERS or not _ID.fullmatch(status_id):
            raise ValueError("verified X receipts require a direct X/FxTwitter status")
        if not _ID.fullmatch(author_id) or not _HANDLE.fullmatch(handle):
            raise ValueError("verified X receipts require stable author identities")
        url = f"https://x.com/{handle}/status/{status_id}"
        return self._issue(
            provider, status_id, url, author_id, handle, content,
            published_at, fetched_at, raw_payload, response_identity,
        )

    def official_document(
        self,
        *,
        provider: EvidenceProvider,
        document_id: str,
        canonical_url: str,
        author_id: str,
        author_handle: str,
        content: str,
        published_at: datetime,
        fetched_at: datetime,
        raw_payload: bytes,
        response_identity: str,
    ) -> VerifiedSourceReceipt:
        provider = EvidenceProvider(provider)
        parsed = urlsplit(canonical_url)
        if provider not in _DOCUMENT_PROVIDERS or not _DOC_ID.fullmatch(document_id):
            raise ValueError("verified documents require stable official identities")
        if parsed.scheme != "https" or not parsed.hostname or parsed.fragment:
            raise ValueError("official document canonical_url must be HTTPS")
        return self._issue(
            provider, document_id, canonical_url, author_id,
            author_handle.strip().lstrip("@").casefold(), content,
            published_at, fetched_at, raw_payload, response_identity,
        )

    def telegram_message(
        self,
        *,
        channel: str,
        message_id: int,
        content: str,
        published_at: datetime,
        fetched_at: datetime,
        raw_payload: bytes,
        response_identity: str,
    ) -> VerifiedSourceReceipt:
        normalized = channel.strip().lstrip("@").casefold()
        if not _TELEGRAM_CHANNEL.fullmatch(normalized):
            raise ValueError("verified Telegram receipts require a public channel")
        if isinstance(message_id, bool) or message_id <= 0:
            raise ValueError("verified Telegram receipts require an exact message")
        source_id = f"telegram:{normalized}:{message_id}"
        return self._issue(
            EvidenceProvider.TELEGRAM_PUBLIC,
            source_id,
            f"https://t.me/{normalized}/{message_id}",
            normalized,
            normalized,
            content,
            published_at,
            fetched_at,
            raw_payload,
            response_identity,
        )

    def _issue(
        self,
        provider: EvidenceProvider,
        source_id: str,
        canonical_url: str,
        author_id: str,
        author_handle: str,
        content: str,
        published_at: datetime,
        fetched_at: datetime,
        raw_payload: bytes,
        response_identity: str,
    ) -> VerifiedSourceReceipt:
        published = _utc(published_at, "published_at")
        fetched = _utc(fetched_at, "fetched_at")
        body = content.strip()
        identity = response_identity.strip()
        if published > fetched or not body or not identity:
            raise ValueError("source receipt chronology and content are required")
        if not isinstance(raw_payload, bytes) or not 1 <= len(raw_payload) <= 2_000_000:
            raise ValueError("bounded raw source bytes are required")
        values = {
            "provider": provider,
            "source_id": source_id,
            "canonical_url": canonical_url,
            "author_id": author_id.strip(),
            "author_handle": author_handle,
            "published_at": published,
            "fetched_at": fetched,
            "content_sha256": sha256(body.encode()).hexdigest(),
            "raw_payload_sha256": sha256(raw_payload).hexdigest(),
            "response_identity": identity,
            "_content": body,
            "_raw_payload": raw_payload,
        }
        receipt = object.__new__(VerifiedSourceReceipt)
        for name, value in values.items():
            object.__setattr__(receipt, name, value)
        object.__setattr__(receipt, "_seal", _seal(values))
        return receipt


def verify_source_receipt(receipt: VerifiedSourceReceipt) -> bool:
    if not isinstance(receipt, VerifiedSourceReceipt):
        return False
    try:
        values = {name: getattr(receipt, name) for name in (
            "provider", "source_id", "canonical_url", "author_id", "author_handle",
            "published_at", "fetched_at", "content_sha256", "raw_payload_sha256",
            "response_identity", "_content", "_raw_payload",
        )}
        return (
            receipt.provider is not EvidenceProvider.GROK_CITATION
            and receipt.content_sha256 == sha256(receipt._content.encode()).hexdigest()
            and receipt.raw_payload_sha256 == sha256(receipt._raw_payload).hexdigest()
            and hmac.compare_digest(receipt._seal, _seal(values))
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _seal(values: dict[str, object]) -> str:
    safe = {
        key: (
            value.value if isinstance(value, EvidenceProvider)
            else value.isoformat() if isinstance(value, datetime)
            else value.hex() if isinstance(value, bytes)
            else value
        )
        for key, value in values.items()
    }
    encoded = json.dumps(safe, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SEAL_KEY, encoded, sha256).hexdigest()


_TRUSTED_RECEIPT_ISSUER = _ReceiptIssuer()
