from debot4.v6.golden_dogs.grok_journal import (
    prompt_is_complete,
    reusable_x_verification_rows,
    successful_candidate_urls,
    successful_prompt_digests,
)


def test_successful_journal_requires_matching_prompt_not_only_reused_key() -> None:
    completed = successful_prompt_digests((
        '{"key":"batch-1","prompt_sha256":"aaa","status":"success"}',
        '{"key":"batch-2","prompt_sha256":"bbb","status":"error"}',
    ))
    assert prompt_is_complete(completed, "batch-1", "aaa") is True
    assert prompt_is_complete(completed, "batch-1", "changed") is False
    assert prompt_is_complete(completed, "batch-2", "bbb") is False


def test_latest_successful_digest_wins_for_append_only_retry_history() -> None:
    completed = successful_prompt_digests((
        '{"key":"batch-1","prompt_sha256":"old","status":"success"}',
        '{"key":"batch-1","prompt_sha256":"new","status":"success"}',
    ))
    assert completed == {"batch-1": "new"}


def test_successful_urls_are_monotonic_when_batch_key_is_reused() -> None:
    urls = successful_candidate_urls((
        '{"key":"batch-1","status":"success","candidate_urls":["old"]}',
        '{"key":"batch-1","status":"error","candidate_urls":["ignored"]}',
        '{"key":"batch-1","status":"success","candidate_urls":["new","old"]}',
    ))
    assert urls == ("new", "old")


def test_x_verification_cache_keeps_terminal_checks_and_retries_unavailable() -> None:
    rows = reusable_x_verification_rows((
        '{"schema":"s","status_url":"u1","status":"verified"}',
        '{"schema":"s","status_url":"u2","status":"status_author_mismatch"}',
        '{"schema":"s","status_url":"u3","status":"status_unavailable"}',
        '{"schema":"old","status_url":"u4","status":"verified"}',
    ), desired_urls=("u1", "u2", "u3", "u4", "u5"), schema="s")

    assert set(rows) == {"u1", "u2"}
