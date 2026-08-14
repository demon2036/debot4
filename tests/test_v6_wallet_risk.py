from debot4.v6.golden_dogs.wallet_risk import (
    has_manipulative_wallet_tag,
    manipulative_wallet_tags,
)


def test_wallet_risk_rule_normalizes_all_authoritative_tags() -> None:
    tags = ("GMGN", " Wash_Trader ", "SANDWICH_BOT", "sybil")
    assert manipulative_wallet_tags(tags) == (
        "sandwich_bot", "sybil", "wash_trader",
    )
    assert has_manipulative_wallet_tag(tags) is True


def test_unrelated_provider_tags_do_not_imply_manipulation() -> None:
    assert has_manipulative_wallet_tag(("kol", "top_followed")) is False
