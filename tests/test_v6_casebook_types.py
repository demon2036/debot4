from __future__ import annotations

import pytest

from debot4.v6.narrative.casebook_types import case, evidence


CA = "0x1111111111111111111111111111111111111111"


def test_casebook_records_preserve_auditable_evidence() -> None:
    item = case(
        "bsc-example",
        "bsc",
        "EXAMPLE",
        CA,
        "2026-08-11T12:00:00Z",
        "historical research only",
        "peak is a market-cap proxy, not an executable quote",
        peak=1_500_000,
        multiple=3.0,
        drawdown=40,
        evidence_items=(
            evidence(
                "x",
                "example actor",
                "early_binding",
                "launch",
                "verified",
                "The post contains the exact contract address.",
                url="https://x.com/example/status/123",
                actor="example",
                at="2026-08-11T12:00:00Z",
                exact_ca=True,
                monitor=True,
            ),
        ),
        risks=("historical liquidity is not reconstructed",),
    )

    payload = item.as_public_dict()

    assert payload["asset_ref"] == CA
    assert payload["peak_proxy_usd"] == 1_500_000
    assert payload["evidence"][0]["role"] == "early_binding"
    assert payload["evidence"][0]["monitor"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("asset_ref", "0x1234"),
        ("first_seen_at", "2026-08-11T12:00:00"),
        ("peak", -1),
        ("drawdown", 101),
    ],
)
def test_casebook_rejects_invalid_metrics_and_identity(
    field: str,
    value: object,
) -> None:
    values: dict[str, object] = {
        "asset_ref": CA,
        "first_seen_at": "2026-08-11T12:00:00Z",
        "peak": 1,
        "drawdown": 1,
    }
    values[field] = value

    with pytest.raises(ValueError):
        case(
            "bad",
            "bsc",
            "BAD",
            values["asset_ref"],
            values["first_seen_at"],
            "test",
            "test",
            peak=values["peak"],
            drawdown=values["drawdown"],
        )


def test_monitored_evidence_requires_an_actor() -> None:
    with pytest.raises(ValueError, match="actor handle"):
        evidence(
            "x",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "No actor identity is available.",
            monitor=True,
        )
