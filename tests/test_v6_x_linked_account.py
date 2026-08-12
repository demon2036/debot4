import pytest

from debot4.v6.golden_dogs.x_linked_account import XLinkedAccountEvidence


def test_profile_disclosed_secondary_account_keeps_both_stable_ids() -> None:
    item = XLinkedAccountEvidence(
        source_handle="main_alpha", source_user_id="123456",
        linked_handle="lowcap_alt", linked_user_id="654321",
        relationship_claim="lowcap second -> @lowcap_alt",
        evidence_url="https://api.fxtwitter.com/main_alpha",
        payload_sha256="a" * 64, reciprocal=True,
    )
    assert item.target_identity_verified is True
    assert item.reciprocal is True


def test_similar_name_or_missing_profile_receipt_cannot_be_link_evidence() -> None:
    with pytest.raises(ValueError, match="fetched X profile"):
        XLinkedAccountEvidence(
            source_handle="main", source_user_id="123456",
            linked_handle="main2", linked_user_id=None,
            relationship_claim="looks similar", evidence_url="https://x.com/main",
            payload_sha256="a" * 64, reciprocal=False,
        )


def test_self_disclosed_alt_without_old_handle_does_not_invent_target() -> None:
    item = XLinkedAccountEvidence(
        source_handle="current_alt", source_user_id="123456",
        linked_handle=None, linked_user_id=None,
        relationship_claim="main account suspended; continuing on this alt",
        evidence_url="https://api.fxtwitter.com/current_alt",
        payload_sha256="a" * 64, reciprocal=False,
    )
    assert item.named_target is False
    assert item.target_identity_verified is False


def test_one_way_affiliation_does_not_become_reciprocal_identity_proof() -> None:
    item = XLinkedAccountEvidence(
        source_handle="researcher", source_user_id="123456",
        linked_handle="known_kol", linked_user_id="654321",
        relationship_claim="one in @known_kol",
        evidence_url="https://api.fxtwitter.com/researcher",
        payload_sha256="b" * 64, reciprocal=False,
    )
    assert item.target_identity_verified is True
    assert item.reciprocal is False
