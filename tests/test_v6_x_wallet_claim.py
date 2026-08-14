import pytest

from debot4.v6.golden_dogs.x_wallet_claim import (
    XProfileWalletClaim,
    XWalletClaimVerdict,
    corroborated_claim_from_mapping,
)


def claim(**changes) -> XProfileWalletClaim:
    values = {
        "handle": "ExactX", "stable_user_id": "123456",
        "wallet": "0x" + "a" * 40,
        "profile_url": "https://api.fxtwitter.com/ExactX",
        "profile_payload_sha256": "b" * 64,
    }
    values.update(changes)
    return XProfileWalletClaim(**values)


def test_profile_wallet_is_preserved_without_inventing_provider_binding() -> None:
    item = claim(provider_handles=(), provider_bound=False)
    assert item.verdict is XWalletClaimVerdict.SELF_DISCLOSED
    assert item.usable_as_provider_wallet_x_binding is False


def test_matching_bound_provider_handle_corroborates_claim() -> None:
    item = claim(provider_handles=("@exactx",), provider_bound=True)
    assert item.verdict is XWalletClaimVerdict.PROVIDER_CORROBORATED
    assert item.usable_as_provider_wallet_x_binding is True


def test_wallet_claim_needs_direct_profile_receipt() -> None:
    with pytest.raises(ValueError, match="directly fetched"):
        claim(profile_url="https://x.com/ExactX")


def test_persisted_claim_is_revalidated_before_binding_use() -> None:
    row = {
        "handle": "ExactX", "stable_user_id": "123456",
        "wallet": "0x" + "a" * 40,
        "profile_url": "https://api.fxtwitter.com/ExactX",
        "profile_payload_sha256": "b" * 64,
        "provider_handles": ["exactx"], "provider_bound": True,
        "verdict": "PROVIDER_CORROBORATED",
    }
    assert corroborated_claim_from_mapping(row) == claim(
        provider_handles=("exactx",), provider_bound=True,
    )
    row["provider_bound"] = False
    with pytest.raises(ValueError, match="verdict disagrees"):
        corroborated_claim_from_mapping(row)
