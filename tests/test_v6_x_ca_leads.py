from datetime import datetime, timezone
from decimal import Decimal

from debot4.v6.golden_dogs.models import Observation
from debot4.v6.golden_dogs.x_ca_leads import (
    exact_evm_addresses,
    join_verified_x_to_markets,
    verified_leads_from_row,
)


UTC = timezone.utc
CA = "0x1234567890abcdef1234567890abcdef12345678"


def test_verified_x_ca_requires_stable_identity_and_receipts() -> None:
    row = {
        "status": "verified", "text": f"BSC CA: {CA}",
        "published_at": "2026-08-01T01:00:00Z",
        "observed_handle": "Caller", "observed_author_id": "123456",
        "profile_user_id": "123456",
        "canonical_url": "https://x.com/Caller/status/123456789",
        "status_payload_sha256": "a" * 64, "profile_payload_sha256": "b" * 64,
    }
    leads = verified_leads_from_row(row)
    assert len(leads) == 1
    assert leads[0].address == CA
    assert verified_leads_from_row({**row, "profile_user_id": "654321"}) == ()
    assert verified_leads_from_row({**row, "status_payload_sha256": ""}) == ()


def test_exact_ca_extraction_rejects_longer_hex_and_deduplicates() -> None:
    text = f"{CA} {CA.upper().replace('0X', '0x')} {CA}f"
    assert exact_evm_addresses(text) == (CA,)


def test_market_join_classifies_timing_without_claiming_a_buy() -> None:
    row = {
        "status": "verified", "text": f"CA {CA}",
        "published_at": "2026-08-01T01:00:00Z",
        "observed_handle": "caller", "observed_author_id": "123456",
        "profile_user_id": "123456",
        "canonical_url": "https://x.com/caller/status/123456789",
        "status_payload_sha256": "a" * 64, "profile_payload_sha256": "b" * 64,
    }
    observation = Observation(
        chain="bsc", address=CA, name="Token", symbol="T", launchpad="flap",
        created_at=1_785_545_000, window_start=1_785_542_400,
        window_end_exclusive=1_786_147_200, first_trade_at=1_785_545_000,
        first_price_usd=Decimal("0.0001"), peak_at=1_785_600_000,
        peak_price_usd=Decimal("0.001"), total_supply=Decimal("1000000000"),
        supply_source="market_current_total_supply", initial_fdv_usd=Decimal("100000"),
        approx_peak_fdv_usd=Decimal("1000000"), peak_multiple=Decimal("10"),
        tiers=("3x", "10x"), meets_peak_threshold=True, current_kols=1, max_kols=2,
        precision="test", status="complete", receipts=(),
    )
    joins = join_verified_x_to_markets(
        verified_leads_from_row(row), {("bsc", CA): observation},
    )
    assert len(joins) == 1
    assert joins[0].timing == "pre_peak"
