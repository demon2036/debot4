#!/usr/bin/env python3
"""Render the audited 13-project / 32-wave attribution ledger in Chinese."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

from render_bsc_week_signal_sections import (
    actor_leads_section, duration, narrative_source_line, wallet_screen_section,
)


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "bsc_week_wave_attributions.jsonl"
SUMMARY = ROOT / "bsc_week_wave_attribution_summary.json"
THEORY = ROOT / "bsc_week_theoretical_capture_summary.json"
ACTORS = ROOT / "bsc_week_advance_actor_leads.jsonl"
OUTPUT = ROOT / "BSC_WEEK_2026-08-06_WAVE_ATTRIBUTION.md"
ORDER = (
    "CETS", "Asian games", "bStocks", "BOT", "fourclub", "bNS", "月薪喵",
    "TKM", "Racoonzilla", "XchangetheWorld", "CSI", "SpaceXcoin", "币安城",
)
CAPTURE = {
    "public_before_1_02": "至少一条经复核公开信号早于 +2%",
    "previous_block_only_before_1_02": "仅前一区块资金可普通确认",
    "same_block_pending_or_builder_only": "仅同块待打包/Builder 理论可提前",
}
DRIVER = {
    "same_block_capital_first": "同块资本先行",
    "previous_block_capital_first": "前一区块资本先行",
    "capital_then_social_amplification": "资本点火后社交放大",
    "fresh_public_thesis_and_market_flow": "新鲜公开论点 + 市场资金流",
    "project_operations_and_market_flow": "项目运营 + 市场资金流",
    "standing_narrative_and_market_flow": "旧叙事站岗 + 市场资金流",
    "unresolved_market_repricing": "未解市场重定价",
}
CONFIDENCE = {
    "medium_high": "中高", "medium": "中", "medium_low": "中低", "low": "低",
}


def main() -> None:
    rows = _jsonl(INPUT)
    actors = _jsonl(ACTORS)
    summary, theory = _json(SUMMARY), _json(THEORY)
    if len(rows) != 32 or summary["wave_count"] != 32:
        raise RuntimeError("refuse to render an incomplete wave ledger")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["label"]].append(row)
    if set(grouped) != set(ORDER):
        raise RuntimeError("report project set mismatch")
    lines = _header(summary, theory, grouped)
    lines.extend(actor_leads_section(actors))
    lines.extend(wallet_screen_section(theory))
    for label in ORDER:
        project = sorted(grouped[label], key=lambda row: row["wave_number"])
        lines.extend(_project(label, project))
    lines.extend(_limits())
    OUTPUT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _header(summary, theory, grouped):
    counts = summary["capture_class_counts"]
    leads = summary["public_closest_lead_bucket_counts"]
    sources = summary["narrative_source_target_counts"]
    return [
        "# BSC 金狗 13 标的 / 32 波逐波归因（2026-08-06—2026-08-13 UTC）",
        "",
        "> 结论先行：本报告只把首个精确交易达到回放基线 `1.02x` 之前的机器可观测事件称为“提前”。时间领先不等于因果，更不等于可买。",
        "",
        "## 第一性原理结论",
        "",
        "```text",
        "32 个胜者波段",
        f"├── {counts['public_before_1_02']} 波：至少一条经语义复核公开信号早于 +2%",
        f"├── {counts['previous_block_only_before_1_02']} 波：公开面为空，但前一区块资金可在确认后看到",
        f"└── {counts['same_block_pending_or_builder_only']} 波：首动与 +2% 同块，只能靠待打包流/Builder 理论看见",
        "```",
        "",
        "公开覆盖 21 波的最近一条信号提前量（避免把数日前旧帖冒充临拉爆点）：",
        "",
        "```text",
        f"<1m {leads.get('lt_60s', 0)} ｜ 1–5m {leads.get('60s_to_lt_300s', 0)} ｜ "
        f"5–30m {leads.get('300s_to_lt_1800s', 0)} ｜ 30m–6h {leads.get('1800s_to_lt_21600s', 0)} ｜ "
        f"6–24h {leads.get('21600s_to_lt_86400s', 0)} ｜ ≥24h {leads.get('gte_86400s', 0)}",
        "```",
        "",
        f"因此，普通确认流零延迟理论上限是 **{theory['conclusions']['ordinary_post_confirmation_ceiling_at_zero_latency']}**，5 秒延迟是 **{theory['conclusions']['ordinary_post_confirmation_ceiling_at_five_seconds']}**；"
        "只有理想化零延迟 pending/Builder 全覆盖才达到 **32/32 原始事件可见**。这不是 32/32 可盈利预测：当前点时合格 KOL/聪明钱包仍为 **0**。",
        "",
        "`fresh/standing` 只保留为 replay 状态字段：后续波以此前有效波 reset 分界，首波以创建时间分界。它不等于“临拉新爆点”；是否接近启动请以最近提前秒数和逐波人工判断为准。",
        "",
        f"叙事源审计：13 个项目中，`{sources['verified_upstream_source']}` 个有可直验上游题材源，"
        f"`{sources['meaningful_exact_ca_publication']}` 个能定位首个有意义 Exact-CA 公开帖；"
        f"但创建前已有有意义 Exact-CA 帖的是 **{sources['meaningful_exact_ca_before_creation']}/13**。",
        "",
        "## 固定口径",
        "",
        "- 窗口：`2026-08-06 00:00:00 ≤ t < 2026-08-13 00:00:00 UTC`。",
        "- 有效波：从局部低点至少 `2x`，5 分钟 close 峰值 FDV 代理至少 `$500K`，回撤 `60%` 后重置。",
        "- 最高值：`5m high × 当前 supply` 的固定窗口 FDV 代理，不是可成交市值。",
        "- 逐笔价格：从基线建立扫描至 `2x` 突破 K 线结束后 60 秒；若 1m OHLC high 与逐笔成交分歧，两者并列并把差异记为反证。",
        "- 头像/banner：CDN 资源时间只作线索，永不单独作为 UI 换图或因果证明。",
        "- KOL：scanner、recap、relay、reply、钓鱼和峰后喊话不算提前 KOL；钱包 provider 标签也不等于历史技能合格。",
        "",
        "## 标的总览",
        "",
        "| 标的 | Exact CA | 窗口最高 FDV 代理 | 波段 |",
        "|---|---|---:|---:|",
        *_overview(grouped),
        "",
    ]


def _overview(grouped):
    lines = []
    for label in ORDER:
        rows = grouped[label]
        ath = rows[0]["market"]["fixed_window_ath_proxy"]["fdv_usd"]
        lines.append(f"| {label} | `{rows[0]['address']}` | {_usd(ath)} | {len(rows)} |")
    return lines


def _project(label, rows):
    lines = [f"## {label}", ""]
    for row in rows:
        lines.extend(_wave(row))
    return lines


def _wave(row):
    market, review = row["market"], row["manual_review"]
    minute = market["minute_boundary"]
    pre, ascent = row["chain_evidence"]["pre_trough"], row["chain_evidence"]["ascent"]
    flow = row["chain_evidence"]["observed_pre_1_20_buy_flow"]
    source_audit = row["narrative_source_audit"]
    flow_text = "缺少完整 +20% 跨越流"
    if flow:
        flow_text = f"{flow['buy_count']} 买 / {_usd(flow['gross_buy_usd'])} / {flow['unique_wallet_count']} 钱包"
    lead = row["advance_public"]["closest_lead_seconds"]
    lead_text = "无公开提前信号" if lead is None else duration(int(lead))
    lines = [
        f"### 波 {row['wave_number']} — {CAPTURE[row['capture_class']]}", "",
        f"行情：`{_time(market['trough_at'])}` 低点 → `{_time(market['peak_at'])}` 峰值，"
        f"`{float(market['multiple']):.2f}x`，峰值 close-FDV {_usd(market['peak_fdv_usd'])}；"
        f"首个交易级 +2% `{_cross_time(market['first_1_02'])}`；"
        f"1m +20% 边界 `{_minute_cross(minute['motion'])}`。",
        "",
        "```text",
        f"最早叙事源 ─ {review['narrative_source']}",
        f"├── 官号/头像 ─ {review['official_or_avatar']}",
        f"├── +2% 前信号 ─ {review['advance_signal']}",
        f"├── 链上点火 ─ {review['chain_ignition']}",
        f"├── 上升传播 ─ {review['propagation']}",
        f"└── 峰后内容 ─ {review['post_peak']}",
        "```",
        "",
        narrative_source_line(source_audit),
        "",
        f"证据计数：公开提前 `fresh={row['advance_public']['fresh_count']}` / "
        f"`standing={row['advance_public']['standing_count']}` / 最近提前 `{lead_text}`；"
        f"+20% 前观测流 `{flow_text}`；"
        f"过滤后标记买入 `pre30={pre['clean_buy_count']}/{_usd(pre['clean_amount_usd'])}`，"
        f"`ascent={ascent['clean_buy_count']}/{_usd(ascent['clean_amount_usd'])}`。",
        "",
        f"最佳支持机制：**{DRIVER[review['best_supported_driver']]}**；置信度：**{CONFIDENCE[review['confidence']]}**。",
        "",
        "反证：" + "；".join(review["counterevidence"]) + "。",
        "",
        "未知项：" + "；".join(review["unknowns"]) + "。",
        "",
    ]
    evidence = _evidence(row)
    if evidence:
        lines.extend(["可直连证据（完整回执见 JSONL 账本）：", "", *evidence, ""])
    return lines


def _evidence(row):
    items = []
    closest = row["advance_public"]["closest_event"]
    if closest:
        items.append((
            _iso(int(closest["occurred_at"])), closest["source"],
            f"closest-public-before-1.02/{duration(int(closest['seconds_to_first_1_02']))}",
            closest["evidence_url"],
        ))
    for source in row["narrative_evidence"]:
        if source["status_url"]:
            items.append((source["published_at"] or "", source["author_handle"],
                          source["relation"], source["status_url"]))
    for key in ("x_evidence_by_phase", "social_evidence_by_phase"):
        for phase in ("historical_baseline", "pre_trough", "ascent", "decay"):
            for event in row[key][phase]:
                role = event.get("semantic") or event.get("action_kind")
                items.append((event["occurred_at"], event["actor"], f"{phase}/{role}", event["url"]))
    seen, output = set(), []
    for at, actor, role, url in sorted(items, key=lambda item: (
        not item[2].startswith("closest-public"), item[0], item[3]
    )):
        if url in seen:
            continue
        seen.add(url)
        output.append(f"- [{actor} · {role} · {at}]({url})")
        if len(output) == 8:
            break
    for buy in row["chain_evidence"]["strict_pre_1_02_block_buys"][:2]:
        tx = buy["provider_buy"]["transaction_hash"]
        timing = buy["block_timing"]["stage"]
        output.append(f"- [BscScan · {timing} · {tx[:10]}…](https://bscscan.com/tx/{tx})")
    return output


def _limits():
    return [
        "## 完整性与未解决风险", "",
        "```text",
        "本报告已覆盖 13/13 标的、32/32 有效波",
        "├── 行情：5m 波段 + 交易级 +2%/+20% 跨越",
        "├── 社交：98 个帖子×CA 人工语义、官号动作、TG 直连回执",
        "├── 链上：RPC 区块位置、前一区块/同块边界、过滤后标记买入",
        "└── 归因：主因、置信度、反证、未知项逐波齐全",
        "```", "",
        "仍不能保证私有 bundle、删除帖、封闭 TG/微信群或未索引内容的完整性；也不能从 13 个胜者反推假阳性、滑点或盈利。"
        "下一步在线系统若要追求原始事件 32/32 可见，必须接 BSC pending/Builder + 全新币创建流；若要追求可交易信号，则还必须在全市场失败样本上完成钱包/KOL 点时精度门禁。",
        "",
        "权威机器账本：`bsc_week_wave_attributions.jsonl`；人工判断：`bsc_week_wave_attribution_reviews.jsonl`；完整性摘要：`bsc_week_wave_attribution_summary.json`。",
    ]


def _time(value):
    return datetime.fromtimestamp(int(value), timezone.utc).strftime("%m-%d %H:%M UTC")


def _cross_time(value):
    return "缺失" if not value else _time(value["occurred_at"])


def _minute_cross(value):
    return "缺失" if not value else (
        f"{_time(value['crossing_bar_at'])} candle（严格提前截止 {_time(value['crossing_before'])}）"
    )


def _usd(value):
    number = float(value)
    if number >= 1_000_000:
        return f"${number / 1_000_000:.3f}M"
    if number >= 1_000:
        return f"${number / 1_000:.1f}K"
    return f"${number:.0f}"


def _iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8",
    ).splitlines() if line.strip()]


if __name__ == "__main__":
    main()
