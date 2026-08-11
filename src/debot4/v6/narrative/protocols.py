"""Network ports implemented by production clients or deterministic fakes."""

from __future__ import annotations

from typing import Protocol

from .fxtwitter import FxTwitterTweet


class StatusFetcher(Protocol):
    def fetch_status(self, status_url: str) -> FxTwitterTweet:
        """Fetch one exact X status without browser automation."""
