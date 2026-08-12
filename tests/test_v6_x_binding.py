from debot4.v6.golden_dogs.x_binding import (
    WalletXIdentity,
    XBindingVerdict,
    assess_x_binding,
)


WALLET = "0x" + "a" * 40


def identity(**changes):
    values = {
        "wallet": WALLET,
        "provider_activity_handle": "Exact_X",
        "public_profile_handle": "exact_x",
        "stat_profile_handle": "@EXACT_X",
        "provider_bound": True,
        "fxtwitter_handle": "exact_x",
        "fxtwitter_user_id": "123456",
    }
    values.update(changes)
    return WalletXIdentity(**values)


def test_x_binding_requires_three_provider_surfaces_and_public_profile() -> None:
    result = assess_x_binding(identity())
    assert result.verdict is XBindingVerdict.PASS
    assert result.canonical_handle == "exact_x"


def test_provider_handle_conflict_rejects_binding() -> None:
    result = assess_x_binding(identity(stat_profile_handle="different"))
    assert result.verdict is XBindingVerdict.REJECT
    assert result.reasons == ("provider_x_handles_conflict",)


def test_missing_surface_or_fxtwitter_profile_stays_pending() -> None:
    assert assess_x_binding(
        identity(stat_profile_handle=None),
    ).verdict is XBindingVerdict.WAIT
    assert assess_x_binding(
        identity(fxtwitter_user_id=None),
    ).verdict is XBindingVerdict.WAIT
