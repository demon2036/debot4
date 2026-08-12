"""Bounded HTTP adapter for official public product resources."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import html
import re
from typing import Callable, Protocol
import urllib.error
import urllib.parse
import urllib.request

from .rules import PublicResourceSnapshot


_RESOURCE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_EVM_CA = re.compile(r"0x[a-fA-F0-9]{40}")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_PLAIN_TITLE = re.compile(r"^Title:\s*(.+?)\s*$", re.I | re.M)
_URL = re.compile(r"https://[^\s\"'<>\\]+", re.I)
_ATTRIBUTE = re.compile(r"(?:href|src)=[\"']([^\"'#]+)[\"']", re.I)
_LOC = re.compile(r"<loc[^>]*>(.*?)</loc>", re.I | re.S)
_ALLOWED_TYPES = (
    "text/", "application/json", "application/xml", "application/xhtml+xml",
    "application/javascript", "application/ld+json",
)
_USER_AGENT = "DeBot4PublicResourceMonitor/1.0"


class PublicResourceError(RuntimeError):
    """A public resource could not be sampled safely."""


class RequestOpener(Protocol):
    def open(self, request: urllib.request.Request, *, timeout: float) -> object: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


@dataclass(frozen=True, slots=True)
class PublicResourceTarget:
    resource_id: str
    actor_id: str
    actor_role: str
    source_url: str
    watched_terms: tuple[str, ...]
    fetch_url: str = ""

    def __post_init__(self) -> None:
        resource_id = self.resource_id.strip().casefold()
        parsed = urllib.parse.urlsplit(self.source_url)
        fetch = urllib.parse.urlsplit(self.fetch_url or self.source_url)
        terms = tuple(dict.fromkeys(
            item.strip().casefold() for item in self.watched_terms if item.strip()
        ))
        if not _RESOURCE_ID.fullmatch(resource_id):
            raise ValueError("public resource target ID is invalid")
        if not self.actor_id.strip() or not self.actor_role.strip() or not terms:
            raise ValueError("public resource target metadata is incomplete")
        if (
            parsed.scheme != "https" or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in {None, 443} or parsed.fragment
        ):
            raise ValueError("public resource target URL is invalid")
        if (
            fetch.scheme != "https" or not fetch.hostname
            or fetch.username is not None or fetch.password is not None
            or fetch.port not in {None, 443} or fetch.fragment
        ):
            raise ValueError("public resource fetch URL is invalid")
        if len(terms) > 64 or any(len(item) > 120 for item in terms):
            raise ValueError("public resource watched terms are invalid")
        object.__setattr__(self, "resource_id", resource_id)
        object.__setattr__(self, "watched_terms", terms)


@dataclass(slots=True)
class PublicResourceClient:
    opener: RequestOpener | None = None
    timeout_seconds: float = 8.0
    max_response_bytes: int = 2_000_000
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or not 1_024 <= self.max_response_bytes <= 8_000_000:
            raise ValueError("public resource limits are invalid")
        if self.opener is None:
            self.opener = urllib.request.build_opener(_NoRedirect())

    def fetch(self, target: PublicResourceTarget) -> PublicResourceSnapshot:
        fetch_url = target.fetch_url or target.source_url
        request = urllib.request.Request(
            fetch_url,
            headers={
                "Accept": "text/html,application/json,application/xml,text/plain,*/*;q=0.5",
                "User-Agent": _USER_AGENT,
            },
        )
        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                if response.geturl() != fetch_url or int(response.status) != 200:
                    raise PublicResourceError("public resource returned an unexpected response")
                raw = response.read(self.max_response_bytes + 1)
                content_type = str(response.headers.get("content-type") or "").casefold()
        except PublicResourceError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            raise PublicResourceError("public resource connection failed") from exc
        if not raw or len(raw) > self.max_response_bytes:
            raise PublicResourceError("public resource response size is invalid")
        if not any(content_type.startswith(item) for item in _ALLOWED_TYPES):
            raise PublicResourceError("public resource content type is unsupported")
        observed = self.clock()
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("public resource clock must be timezone-aware")
        text = raw.decode("utf-8", errors="replace")
        folded = text.casefold()
        return PublicResourceSnapshot(
            resource_id=target.resource_id,
            actor_id=target.actor_id,
            actor_role=target.actor_role,
            observed_at=observed,
            source_url=target.source_url,
            evidence_hash=hashlib.sha256(raw).hexdigest(),
            terms=frozenset(item for item in target.watched_terms if item in folded),
            token_addresses=frozenset(
                match.group(0).casefold() for match in _EVM_CA.finditer(text)
            ),
            artifacts=_artifacts(text, target.source_url),
            title=_title(text),
        )


def _title(text: str) -> str:
    match = _TITLE.search(text)
    if match is None:
        match = _PLAIN_TITLE.search(text)
    if match is None:
        return ""
    return re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()


def _artifacts(text: str, base_url: str) -> frozenset[str]:
    values = [match.group(0) for match in _URL.finditer(text)]
    values.extend(match.group(1) for match in _ATTRIBUTE.finditer(text))
    values.extend(html.unescape(match.group(1)).strip() for match in _LOC.finditer(text))
    output: dict[str, None] = {}
    for value in values:
        absolute = urllib.parse.urljoin(base_url, html.unescape(value))
        parsed = urllib.parse.urlsplit(absolute)
        if parsed.scheme == "https" and parsed.hostname:
            output[urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))] = None
        if len(output) >= 5_000:
            break
    return frozenset(output)
