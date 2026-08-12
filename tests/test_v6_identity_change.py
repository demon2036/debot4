from datetime import datetime, timezone

from debot4.v6.identity_change import (
    IdentityChangeMonitor,
    JsonProfileSnapshotStore,
    ProfileMediaReceipt,
    ProfileSnapshot,
    profile_change_events,
    profile_resource_time,
)
from debot4.v6.explosion import ExplosionEventStore
from debot4.v6.x import XProfile, XProfileObservation


SEEN = datetime(2026, 8, 11, 16, 47, 2, tzinfo=timezone.utc)
SOURCE = "https://api.fxtwitter.com/2/profile/bot?about_account=1"


def _snapshot(
    avatar: str,
    banner: str = "",
    *,
    evidence: str = "a" * 64,
    seen: datetime = SEEN,
):
    return ProfileSnapshot(
        "bot", "2085838061347217408", seen, SOURCE, evidence,
        {
            "display_name": "Grok Bot",
            "description": "AI teammates",
            "avatar_url": avatar,
            "avatar_sha256": "1" * 64,
            "banner_url": banner,
            "banner_sha256": "2" * 64 if banner else "",
            "location": "",
            "profile_url": "https://x.com/bot",
            "website_url": "https://x.ai/bot",
            "website_display": "x.ai/bot",
            "verified": True,
            "verification_type": "organization",
            "protected": False,
            "based_in": "United States",
            "username_change_count": 1,
            "username_changed_at": "2026-08-07T22:23:13.595Z",
        },
    )


def test_bot_avatar_and_banner_urls_reveal_provider_times() -> None:
    avatar = (
        "https://pbs.twimg.com/profile_images/2087219239275069440/"
        "KW6C403V_normal.jpg"
    )
    banner = (
        "https://pbs.twimg.com/profile_banners/2085838061347217408/1786466871"
    )

    assert profile_resource_time(avatar).isoformat() == "2026-08-11T16:46:59.958000+00:00"
    assert profile_resource_time(banner).isoformat() == "2026-08-11T16:47:51+00:00"


def test_profile_diff_emits_separate_timed_avatar_and_banner_events() -> None:
    old = _snapshot("https://pbs.twimg.com/profile_images/2085830000000000000/old.jpg")
    new = _snapshot(
        "https://pbs.twimg.com/profile_images/2087219239275069440/new.jpg",
        "https://pbs.twimg.com/profile_banners/2085838061347217408/1786466871",
        evidence="b" * 64,
        seen=datetime(2026, 8, 11, 16, 47, 52, tzinfo=timezone.utc),
    )

    events = profile_change_events(old, new, actor_role="official_product")
    by_type = {item.subtype: item for item in events}

    assert by_type["avatar_url_changed"].occurred_at.isoformat() == (
        "2026-08-11T16:46:59.958000+00:00"
    )
    assert by_type["banner_url_changed"].occurred_at.isoformat() == (
        "2026-08-11T16:47:51+00:00"
    )
    assert all(item.buy_eligible is False for item in events)


class _Profiles:
    def __init__(self, observations: list[XProfileObservation]) -> None:
        self.observations = observations

    def fetch_observation(self, _handle: str) -> XProfileObservation:
        return self.observations.pop(0)


class _Media:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def fetch(self, url: str) -> ProfileMediaReceipt:
        self.urls.append(url)
        return ProfileMediaReceipt(url, SEEN, 10, "3" * 64, "image/jpeg")


def _observation(fetched_at: datetime, evidence: str) -> XProfileObservation:
    profile = XProfile(
        "bot", "2085838061347217408", "Grok Bot", "AI teammates",
        fetched_at,
        avatar_url="https://pbs.twimg.com/profile_images/1/avatar.jpg",
        banner_url="https://pbs.twimg.com/profile_banners/1/2",
    )
    return XProfileObservation(profile, SOURCE, 100, evidence, "cf-ray:test")


def test_monitor_reuses_media_hashes_while_urls_are_unchanged(tmp_path) -> None:
    media = _Media()
    profiles = _Profiles([
        _observation(SEEN, "a" * 64),
        _observation(
            datetime(2026, 8, 11, 16, 47, 3, tzinfo=timezone.utc),
            "b" * 64,
        ),
    ])
    snapshots = JsonProfileSnapshotStore(tmp_path / "profiles.json")
    with ExplosionEventStore(tmp_path / "events.sqlite3") as events:
        monitor = IdentityChangeMonitor(profiles, snapshots, events, media)
        assert monitor.poll("bot", actor_role="official_product") == ()
        assert monitor.poll("bot", actor_role="official_product") == ()

    assert media.urls == [
        "https://pbs.twimg.com/profile_images/1/avatar.jpg",
        "https://pbs.twimg.com/profile_banners/1/2",
    ]
