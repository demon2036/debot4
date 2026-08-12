from __future__ import annotations

from decimal import Decimal
import hashlib
import json

import httpx

from debot4.v6.golden_dogs.collection import collect_source
from debot4.v6.golden_dogs.debot_detail import parse_detail_seed
from debot4.v6.golden_dogs.debot_public import PublicDeBotClient, TokenDetailPage
from debot4.v6.golden_dogs.kol_cases import KOL_TOKEN_CASES
from debot4.v6.golden_dogs.kol_evidence import KOL_WALLET_ATTRIBUTIONS
from debot4.v6.golden_dogs.market_audit import audit_markets
from debot4.v6.golden_dogs.models import Candle, EvidenceReceipt, MarketTrace, TokenSeed
from debot4.v6.golden_dogs.rules import analyze_market
from debot4.v6.golden_dogs.serialization import json_value, observation_from_mapping
from debot4.v6.golden_dogs.weekly_scan import ScanWindow
from datetime import datetime, timezone


CA = "0x" + "a" * 40
RECEIPT = EvidenceReceipt(
    "test_json",
    "https://example.test/evidence",
    1,
    "0" * 64,
)


def seed() -> TokenSeed:
    return TokenSeed(
        chain="bsc",
        address=CA,
        name="Story Dog",
        symbol="DOG",
        launchpad="four_meme",
        created_at=10,
        creator_address="0x" + "b" * 40,
        rank_supply=Decimal("1000000000"),
        current_kols=1,
        max_kols=3,
        social_urls=(),
        discovered_sources=("four_meme",),
    )


def candle(at: int, open_: str, high: str) -> Candle:
    return Candle(
        at,
        Decimal(open_),
        Decimal(high),
        Decimal(open_),
        Decimal(high),
        Decimal("1"),
    )


def test_market_threshold_does_not_require_ten_x() -> None:
    trace = MarketTrace(
        (candle(10, "0.0003", "0.0003"), candle(20, "0.0004", "0.0006")),
        Decimal("1000000000"),
        18,
        RECEIPT,
    )
    result = analyze_market(
        seed(), trace, window_start=1, window_end_exclusive=100,
    )
    assert result.meets_peak_threshold is True
    assert result.peak_multiple == Decimal("2")
    assert result.initial_fdv_usd == Decimal("300000.0000")
    assert result.approx_peak_fdv_usd == Decimal("600000.0000")
    assert result.tiers == ()
    assert result.supply_source == "market_current_total_supply"


def test_large_multiple_below_peak_fdv_is_not_gold() -> None:
    trace = MarketTrace(
        (candle(10, "0.000001", "0.000001"), candle(20, "0.00001", "0.0001")),
        Decimal("1000000"),
        18,
        RECEIPT,
    )
    result = analyze_market(
        seed(), trace, window_start=1, window_end_exclusive=100,
    )
    assert result.peak_multiple == Decimal("100")
    assert result.approx_peak_fdv_usd == Decimal("100.0000")
    assert result.meets_peak_threshold is False


def test_observation_json_round_trip_revalidates_domain_record() -> None:
    trace = MarketTrace(
        (candle(10, "0.0003", "0.0006"),), Decimal("1000000000"), 18, RECEIPT,
    )
    expected = analyze_market(seed(), trace, window_start=1, window_end_exclusive=100)

    assert observation_from_mapping(json_value(expected)) == expected


def test_json_value_serializes_string_enums_as_values() -> None:
    from debot4.v6.golden_dogs.qualification import Verdict

    assert json_value(Verdict.WAIT) == "WAIT"


def test_peak_outside_fixed_window_does_not_qualify() -> None:
    trace = MarketTrace(
        (candle(10, "0.0001", "0.0001"), candle(200, "0.001", "0.01")),
        Decimal("1000000000"),
        18,
        RECEIPT,
    )
    result = analyze_market(
        seed(), trace, window_start=1, window_end_exclusive=100,
    )
    assert result.peak_at == 10
    assert result.approx_peak_fdv_usd == Decimal("100000.0000")
    assert result.meets_peak_threshold is False


class FakePage:
    def __init__(self, rows: tuple[dict, ...]) -> None:
        self.rows = rows
        self.receipt = RECEIPT


class FakeClient:
    def __init__(self) -> None:
        self.queries: list[tuple[int, int]] = []

    def fetch_rank_page(
        self,
        chain: str,
        source: str,
        low: int,
        high: int,
        *,
        limit: int,
    ) -> FakePage:
        self.queries.append((low, high))
        count = limit if high - low > 1 else 1
        rows = tuple(_row(low * 10 + index + 1) for index in range(count))
        return FakePage(rows)


def _row(created_at: int) -> dict:
    return {
        "chain": "bsc",
        "contract": "0x" + f"{created_at:040x}"[-40:],
        "meta": {
            "name": "Dog",
            "symbol": "DOG",
            "launchpad": "four_meme",
            "create_time": created_at,
            "decimals": 18,
            "total_supply": "1000000000000000000000000000",
        },
        "meme_tag_stats": {"kols": 0, "kolsMax": 0},
    }


def test_capped_rank_windows_are_split_until_uncapped() -> None:
    client = FakeClient()
    result = collect_source(client, "bsc", "four_meme", 4, page_limit=2)
    assert result.coverage_complete is True
    assert (0, 4) in client.queries
    assert {(0, 1), (1, 2), (2, 3), (3, 4)} <= set(client.queries)
    assert len(result.tokens) == 4


def test_exact_ca_detail_is_parsed_without_rank_dependency() -> None:
    page = TokenDetailPage(
        {
            "meta": {
                "chain": "robinhood",
                "address": CA,
                "creator_address": "0x" + "b" * 40,
                "symbol": "DOG",
                "name": "Exact Dog",
                "decimals": 18,
                "total_supply": "1000000000000000000000000000",
                "launchpad": "pons",
                "creation_timestamp": 20,
            },
            "social": {"twitter": "https://x.com/exactdog", "description": "not a URL"},
        },
        RECEIPT,
    )
    result = parse_detail_seed(page)
    assert result.rank_supply == Decimal("1000000000")
    assert result.social_urls == ("https://x.com/exactdog",)
    assert result.discovered_sources == ("exact_ca_audit",)


def test_reviewed_kol_cases_keep_corrected_exact_contracts() -> None:
    by_token = {case.token: case.address for case in KOL_TOKEN_CASES}
    assert by_token["MarsCoin"] == "0xfe189e97832da1573e4e4ff034f4ffc3a15c7777"
    assert by_token["STONKBROKER"] == "0xe934e36a439c94017b64a3fece66af12099abf50"
    assert by_token["PONS"] == "0x39dbed3a2bd333467115de45665cc57f813c4571"


def test_market_null_list_is_treated_as_empty_window() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"list": None, "total_supply": "1000000000000000000", "decimals": 18},
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as raw_client:
        client = PublicDeBotClient(client=raw_client)
        result = client.fetch_market("bsc", CA)
    assert result.candles == ()
    assert result.total_supply == Decimal("1")


class RetryingMarketClient:
    calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def fetch_market(self, *_args, **_kwargs):
        type(self).calls += 1
        if type(self).calls == 1:
            raise ValueError("transient schema response")
        return MarketTrace((candle(10, "0.0001", "0.0001"),), Decimal("1000000000"), 18, RECEIPT)


def test_market_audit_retries_a_complete_token_measurement() -> None:
    RetryingMarketClient.calls = 0
    window = ScanWindow(
        datetime.fromtimestamp(1, timezone.utc),
        datetime.fromtimestamp(100, timezone.utc),
    )
    result = audit_markets(
        RetryingMarketClient, (seed(),), {"bsc": (window,)}, workers=1,
    )

    assert result.errors == ()
    assert len(result.observations) == 1
    assert RetryingMarketClient.calls == 2


def test_rank_receipt_fingerprints_exact_filter_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": 0, "data": {"completed": []}},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as raw_client:
        client = PublicDeBotClient(client=raw_client)
        page = client.fetch_rank_page("bsc", "flap", 12, 34, limit=56)
    context = page.receipt.request_context
    assert context is not None
    assert json.loads(context) == {
        "column": "completed",
        "groups": [{
            "filter": {"create_time_minutes": [12, 34]},
            "meme_types": ["bsc:flap"],
        }],
        "limit": 56,
        "sort_field": "",
    }
    assert page.receipt.request_sha256 == hashlib.sha256(context.encode()).hexdigest()


def test_kol_wallet_attribution_uses_wallet_not_token_ca() -> None:
    evidence = KOL_WALLET_ATTRIBUTIONS[0]
    assert evidence.handle == "kenjiquest"
    assert evidence.wallet.endswith("1e31")
    assert evidence.wallet != evidence.token_address
    assert evidence.transfer_amount == Decimal("156947093.381947019125647259")
    assert evidence.transfer_at < evidence.disclosed_at
