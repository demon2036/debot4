"""Official-signal pagination on top of the persistent DeBot transport."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode
from uuid import uuid4

from ..domain import DeBotSignal
from .http import DeBotHttp
from .parser import next_cursor, parse_page


BASE_URL = "https://app.debot.ai/api/community/signal/channel/list"


@dataclass(frozen=True, slots=True)
class DeBotPage:
    signals: tuple[DeBotSignal, ...]
    next_cursor: str | None
    fetched_at: datetime
    bytes_read: int


class DeBotClient:
    def __init__(self, transport: DeBotHttp) -> None:
        self.transport = transport

    def close(self) -> None:
        self.transport.close()

    def fetch_page(self, cursor: str | None = None) -> DeBotPage:
        params = {
            "chain": "bsc",
            "page_size": "32",
            "request_id": str(uuid4()),
        }
        if cursor:
            params["next"] = cursor
        document = self.transport.get_json(f"{BASE_URL}?{urlencode(params)}")
        return DeBotPage(
            parse_page(document.payload, document.fetched_at),
            next_cursor(document.payload),
            document.fetched_at,
            document.bytes_read,
        )
