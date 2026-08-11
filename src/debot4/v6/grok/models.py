"""Small immutable values returned by the Grok2API boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class GrokSearchSource:
    url: str
    title: str
    source_type: str

    def __post_init__(self) -> None:
        url = self.url.strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("search source must be an absolute HTTP URL")
        object.__setattr__(self, "url", url)
        object.__setattr__(self, "title", self.title.strip() or parsed.netloc)
        object.__setattr__(self, "source_type", self.source_type.strip() or "web")


@dataclass(frozen=True, slots=True)
class GrokCitation:
    url: str
    title: str
    start_index: int | None = None
    end_index: int | None = None

    def __post_init__(self) -> None:
        url = self.url.strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("citation must be an absolute HTTP URL")
        if self.start_index is not None and self.start_index < 0:
            raise ValueError("citation start_index cannot be negative")
        if self.end_index is not None and self.end_index < 0:
            raise ValueError("citation end_index cannot be negative")
        object.__setattr__(self, "url", url)
        object.__setattr__(self, "title", self.title.strip() or parsed.netloc)


@dataclass(frozen=True, slots=True)
class GrokSearchAnswer:
    response_id: str
    model: str
    text: str
    sources: tuple[GrokSearchSource, ...]
    citations: tuple[GrokCitation, ...]
    candidate_urls: tuple[str, ...]
    usage: Mapping[str, int]

    def __post_init__(self) -> None:
        if not self.response_id.strip():
            raise ValueError("response_id is required")
        if not self.model.strip():
            raise ValueError("model is required")
        if not self.text.strip():
            raise ValueError("Grok returned no answer text")
        object.__setattr__(self, "text", self.text.strip())
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "citations", tuple(self.citations))
        object.__setattr__(self, "candidate_urls", tuple(self.candidate_urls))
        object.__setattr__(self, "usage", dict(self.usage))

    @property
    def has_sources(self) -> bool:
        return bool(self.sources)
