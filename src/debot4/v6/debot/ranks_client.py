"""Direct DeBot API client for the three BSC meme-ranks stages."""

from __future__ import annotations

from urllib.parse import urlencode
from uuid import uuid4

from .http import DeBotHttp
from .ranks_models import RankPage
from .ranks_parser import STAGE_KEYS, parse_ranks


BASE_URL = "https://app.debot.ai/api/dashboard/meme/v3/ranks"
MEME_TYPES = (
    "four_meme",
    "four_meme_agent",
    "flap",
    "flap_stocks_vault",
    "openfour_creator_incentives",
    "openfour_cubepeg",
    "openfour_likwid",
    "openfour_royalty",
    "cheesepad",
)


class DeBotRanksClient:
    def __init__(self, transport: DeBotHttp) -> None:
        self.transport = transport

    def fetch(self, stage: str) -> RankPage:
        if stage not in STAGE_KEYS:
            raise ValueError("unknown DeBot ranks stage")
        params: list[tuple[str, str]] = [("request_id", str(uuid4()))]
        params.extend(("meme_type", f"bsc:{item}") for item in MEME_TYPES)
        params.extend((
            ("column", stage),
            ("new_filter", "{}"),
            ("completing_filter", "{}"),
            ("completed_filter", "{}"),
        ))
        if stage == "completing":
            params.append(("sort_field", "progress"))
        params.append(("limit", "100"))
        document = self.transport.get_json(f"{BASE_URL}?{urlencode(params)}")
        return RankPage(
            stage=stage,
            snapshots=parse_ranks(document.payload, stage, document.fetched_at),
            fetched_at=document.fetched_at,
            bytes_read=document.bytes_read,
        )
