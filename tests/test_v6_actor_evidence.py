from datetime import datetime, timezone

from debot4.v6.narrative.actor_evidence import (
    ActorEvidenceCandidate,
    verify_actor_evidence,
)
from debot4.v6.narrative.fxtwitter import FxTwitterTweet
from debot4.v6.x import XProfile


NOW = datetime(2026, 8, 10, 20, tzinfo=timezone.utc)
STATUS = "2086727064934068682"


class Profiles:
    def __init__(self, handle: str, user_id: str) -> None:
        self.profile = XProfile(handle, user_id, handle, "reviewed role", NOW)

    def fetch(self, _handle: str) -> XProfile:
        return self.profile


class Statuses:
    def __init__(self, handle: str, user_id: str | None) -> None:
        self.tweet = FxTwitterTweet(
            STATUS,
            handle,
            user_id,
            "exact authored narrative evidence",
            NOW,
            NOW,
            f"https://x.com/{handle}/status/{STATUS}",
        )

    def fetch_status(self, _url: str) -> FxTwitterTweet:
        return self.tweet


def test_rejects_valid_tweet_id_falsely_attributed_to_path_handle() -> None:
    candidate = ActorEvidenceCandidate(
        "CryptoKaleo", f"https://x.com/CryptoKaleo/status/{STATUS}"
    )

    finding = verify_actor_evidence(
        candidate,
        profiles=Profiles("CryptoKaleo", "906234475604037637"),
        statuses=Statuses("theunipcs", "1755899659040555009"),
    )

    assert finding.status == "status_author_mismatch"
    assert finding.observed_handle == "theunipcs"
    assert not finding.verified


def test_accepts_only_exact_author_and_matching_stable_profile_id() -> None:
    candidate = ActorEvidenceCandidate(
        "theunipcs", f"https://x.com/theunipcs/status/{STATUS}"
    )

    finding = verify_actor_evidence(
        candidate,
        profiles=Profiles("theunipcs", "1755899659040555009"),
        statuses=Statuses("theunipcs", "1755899659040555009"),
    )

    assert finding.verified
    assert finding.canonical_url == f"https://x.com/theunipcs/status/{STATUS}"


def test_rejects_profile_identity_drift_even_when_handle_matches() -> None:
    candidate = ActorEvidenceCandidate(
        "theunipcs", f"https://x.com/theunipcs/status/{STATUS}"
    )

    finding = verify_actor_evidence(
        candidate,
        profiles=Profiles("theunipcs", "999999"),
        statuses=Statuses("theunipcs", "1755899659040555009"),
    )

    assert finding.status == "stable_id_mismatch"
    assert not finding.verified
