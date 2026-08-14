import json

from debot4.v6.golden_dogs.x_profile_leads import (
    profile_handle_from_url,
    successful_profile_leads,
)


def test_profile_handle_accepts_profiles_and_statuses_but_rejects_reserved_paths() -> None:
    assert profile_handle_from_url("https://x.com/GCsheng") == "gcsheng"
    assert profile_handle_from_url("https://x.com/GCsheng/status/123") == "gcsheng"
    assert profile_handle_from_url("https://x.com/search?q=meme") is None
    assert profile_handle_from_url("http://x.com/GCsheng") is None


def test_successful_profile_leads_keep_source_tasks_without_promoting_errors() -> None:
    rows = (
        {"status": "success", "key": "a", "answer": "ok", "candidate_urls": [
            "https://x.com/GCsheng", "https://x.com/GCsheng/status/123",
        ]},
        {"status": "error", "key": "b", "candidate_urls": ["https://x.com/fake"]},
    )
    leads = successful_profile_leads(json.dumps(row) for row in rows)

    assert len(leads) == 1
    assert leads[0].handle == "gcsheng"
    assert leads[0].task_keys == ("a",)
    assert len(leads[0].candidate_urls) == 2
