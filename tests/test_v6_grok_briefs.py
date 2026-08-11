from datetime import datetime, timezone
import json

import pytest

from debot4.v6.grok import (
    CaCarrierStatus,
    CatalystType,
    EventRole,
    GrokBriefError,
    NarrativePhase,
    parse_narrative_brief,
)
from debot4.v6.grok.prompts import (
    SYSTEM,
    passive_investigation_prompt,
    proactive_investigation_prompt,
)
from debot4.v6.narrative.research_serializers import brief_payload


CA_ONE = "0x1111111111111111111111111111111111111111"
CA_TWO = "0x2222222222222222222222222222222222222222"
NOW = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


def test_legacy_minimal_json_remains_compatible() -> None:
    text = """事实：原帖可核验。
    {"narrative_key":"Broccoli","one_line_meme":"CZ 的狗故事形成同名 meme", "event_role":"source","why_now":"CZ 刚发布原帖","unknowns":["没有官方 CA"]}
    """

    brief = parse_narrative_brief(text)

    assert brief.narrative_key == "Broccoli"
    assert brief.event_role is EventRole.SOURCE
    assert brief.unknowns == ("没有官方 CA",)
    assert brief.phase is NarrativePhase.UNKNOWN
    assert brief.ca_carrier_status is CaCarrierStatus.UNKNOWN
    assert brief.competing_cas == ()


def test_full_north_star_brief_is_typed_and_serialized() -> None:
    first = {"chain": "BSC", "address": CA_ONE.upper().replace("0X", "0x"), "symbol": "BROC"}
    second = {"chain": "bsc", "address": CA_TWO, "symbol": "BROCCOLI"}
    payload = {
        "narrative_key": "Broccoli",
        "one_line_meme": "CZ 的狗名成为社区争夺的 meme",
        "event_role": "catalyst",
        "narrative_source_summary": "CZ 在新帖中公开了狗名，但没有发布 CA。",
        "why_now": "源头人物刚公开名字，旧猜测第一次获得可核验实体。",
        "propagation_engine": ["CZ 身份带来首轮注意力", "狗的视觉素材便于社区二创"],
        "future_24h_path": ["社区二创扩散", "CZ 是否继续互动决定第二轮传播"],
        "ca_carrier_status": "leaders_split",
        "competing_cas": [first, second],
        "narrative_leader": first,
        "market_leader": second,
        "phase": "discovery",
        "catalyst_type": "ecosystem_actor_action",
        "counter_evidence": ["原帖没有 exact CA"],
        "invalidation_conditions": ["CZ 明确否认同名代币"],
        "unknowns": ["哪个 CA 会形成社区共识"],
    }

    brief = parse_narrative_brief("正文\n" + json.dumps(payload, ensure_ascii=False))
    serialized = brief_payload(brief)

    assert brief.phase is NarrativePhase.DISCOVERY
    assert brief.catalyst_type is CatalystType.ECOSYSTEM_ACTOR_ACTION
    assert brief.ca_carrier_status is CaCarrierStatus.LEADERS_SPLIT
    assert brief.narrative_leader is not None
    assert brief.narrative_leader.address == CA_ONE
    assert brief.market_leader is not None
    assert brief.market_leader.address == CA_TWO
    assert serialized is not None
    assert serialized["propagation_engine"] == list(brief.propagation_engine)
    assert serialized["narrative_leader"] == {
        "chain": "bsc", "address": CA_ONE, "symbol": "BROC"
    }
    assert "score" not in serialized and "buy" not in serialized


@pytest.mark.parametrize(
    "payload",
    (
        {"narrative_key": 7, "one_line_meme": "story"},
        {"narrative_key": "Broccoli", "one_line_meme": "story", "event_role": "buy"},
        {"narrative_key": "Broccoli", "one_line_meme": "story", "unknowns": "none"},
        {"narrative_key": "Broccoli", "one_line_meme": "story", "phase": "early"},
        {"narrative_key": "Broccoli", "one_line_meme": "story", "score": 9},
        {
            "narrative_key": "Broccoli", "one_line_meme": "story",
            "ca_carrier_status": "no_ca",
            "competing_cas": [{"chain": "bsc", "address": CA_ONE, "symbol": "B"}],
        },
        {
            "narrative_key": "Broccoli", "one_line_meme": "story",
            "ca_carrier_status": "open_race",
            "competing_cas": [{"chain": "bsc", "address": CA_ONE, "symbol": "B"}],
        },
    ),
)
def test_invalid_types_enums_trade_directives_and_ca_states_fail_closed(
    payload: dict[str, object],
) -> None:
    with pytest.raises(GrokBriefError):
        parse_narrative_brief(json.dumps(payload))


def test_missing_json_and_array_overflow_fail_closed() -> None:
    with pytest.raises(GrokBriefError):
        parse_narrative_brief("no json here")
    payload = {
        "narrative_key": "Broccoli",
        "one_line_meme": "story",
        "unknowns": [f"unknown-{index}" for index in range(33)],
    }
    with pytest.raises(GrokBriefError):
        parse_narrative_brief(json.dumps(payload))


def test_prompts_require_complete_score_free_narrative_output() -> None:
    prompts = (
        proactive_investigation_prompt(actor="cz_binance", event_text="dog", event_at=NOW),
        passive_investigation_prompt(token_address=CA_ONE, anomaly="sudden rise", observed_at=NOW),
    )

    for prompt in prompts:
        for field in (
            "narrative_source_summary", "why_now", "propagation_engine",
            "future_24h_path", "ca_carrier_status", "competing_cas",
            "narrative_leader", "market_leader", "phase", "catalyst_type",
            "counter_evidence", "invalidation_conditions", "unknowns",
            "evidence_urls",
        ):
            assert field in prompt
        assert "不要用 KOL 数量给叙事打分" in prompt or "反向编造故事" in prompt
    assert "禁止输出分数" in SYSTEM
    assert "BUY/SELL" in SYSTEM
