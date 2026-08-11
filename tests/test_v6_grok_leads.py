from debot4.v6.grok import (
    GrokSearchAnswer,
    extract_x_status_leads,
)


def _answer(*urls: str) -> GrokSearchAnswer:
    return GrokSearchAnswer(
        "response-1",
        "grok-chat-fast",
        "candidate search output",
        (),
        (),
        urls,
        {},
    )


def test_only_exact_numeric_x_status_urls_become_leads() -> None:
    answer = _answer(
        "https://x.com/cz_binance/status/1890071433214038103",
        "https://x.com/cz_binance",
        "https://example.com/cz/status/1890071433214038103",
        "https://x.com/cz_binance/status/fabricated",
    )

    leads = extract_x_status_leads(answer)

    assert len(leads) == 1
    assert leads[0].handle == "cz_binance"
    assert leads[0].status_id == "1890071433214038103"
    assert leads[0].canonical_url == (
        "https://x.com/cz_binance/status/1890071433214038103"
    )


def test_duplicate_mirror_urls_are_one_untrusted_lead() -> None:
    answer = _answer(
        "https://twitter.com/cz_binance/status/1890071433214038103",
        "https://fxtwitter.com/cz_binance/status/1890071433214038103",
    )

    leads = extract_x_status_leads(answer)

    assert len(leads) == 1
    assert leads[0].response_id == "response-1"
