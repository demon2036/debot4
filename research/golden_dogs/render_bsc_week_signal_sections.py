"""Render the advance-actor and point-in-time wallet audit sections."""

from __future__ import annotations


def actor_leads_section(rows):
    independent = [row for row in rows if row["source"] != "x_project"]
    repeated = [row for row in independent if row["fresh_advance_wave_count"] >= 2]
    cross_target = [row for row in independent if row["target_count"] >= 2]
    return [
        "## 提前账号 / 频道线索（不是合格 KOL）", "",
        "以下只证明该公开来源曾早于交易级 +2% 出现。`总覆盖波` 可重复来自同一标的后续波；没有失败样本精度、稳定身份和钱包控制证明，因此全部仍是 discovery lead。", "",
        "| 来源 | 账号/频道 | 总覆盖波 | 新鲜覆盖波 | 跨标的 | 最近提前 | 直接证据 |",
        "|---|---|---:|---:|---:|---:|---|",
        *[
            f"| {row['source']} | `{row['actor']}` | {row['advance_wave_count']} | "
            f"{row['fresh_advance_wave_count']} | {row['target_count']} | "
            f"{duration(int(row['closest_lead_seconds']))} | "
            f"[最近回执]({row['closest_event']['url']}) |"
            for row in independent
        ], "",
        f"结论：独立账号/频道候选 **{len(independent)}** 个；正式新 KOL **0**。"
        f"按本波新鲜信号重复覆盖至少两波的候选 **{len(repeated)}** 个，"
        f"跨两个标的的候选 **{len(cross_target)}** 个。总覆盖多波若只是同币旧帖站岗，不能当作连续预测。", "",
    ]


def wallet_screen_section(theory):
    qualification = theory["qualification"]
    rows = qualification["wallet_screen_results"]
    return [
        "## 钱包点时技能审计（不是聪明钱包名单）", "",
        f"从 {qualification['historical_x_attributed_wallet_leads']} 个历史 X-attributed 候选中，"
        f"只有 {qualification['frequency_screen_pass_wallets']} 个进入完整失败样本审计。"
        f"在信号发生前已成熟的 {qualification['mature_wallet_token_outcomes']} 个 24h 钱包×代币结果中，"
        f"{qualification['measurable_wallet_token_outcomes']} 个可测、{qualification['early_gold_hits']} 个命中，"
        "但没有一个达到最低技能门槛。", "",
        "| 当前 X 绑定 | 钱包 | 点时可测样本 | 命中 | 命中率 | 技能门禁 |",
        "|---|---|---:|---:|---:|---|",
        *[
            f"| `{row['x_handle']}` | `{row['wallet']}` | {row['measurable_tokens']} | "
            f"{row['hits']} | {_percent(row['hit_rate'])} | "
            f"{'PASS' if row['skill_screen_pass'] else 'FAIL'} |"
            for row in rows
        ], "",
        "门槛是至少 10 个点时成熟且可测样本、24h 内同时达到 `2x` 与 `$500K FDV` 的命中率至少 20%。"
        "这些 X 绑定本身仍是当前快照，不足以证明历史时点控制关系。", "",
    ]


def narrative_source_line(audit):
    origins = {
        "verified_upstream_source": "上游叙事源有直连回执",
        "exact_ca_publication_verified_upstream_origin_unresolved": (
            "首个有意义 Exact-CA 帖可核验，但更早原创来源未解"
        ),
        "upstream_candidate_unavailable": "存在已删除上游候选，无法直验",
        "only_non_narrative_exact_ca_observation": "只找到 scanner 等非叙事观察",
        "no_direct_public_source_identified": "未找到可直验公开来源",
    }
    source = audit["earliest_meaningful_exact_ca_publication"]
    exact = "未找到有意义 Exact-CA 公开帖"
    if source is not None:
        relation = source["relation_to_token_creation"]
        lead = abs(int(source["seconds_from_token_creation"]))
        timing = "创建前" if relation == "before_creation" else "创建后"
        exact = (
            f"首个有意义 Exact-CA 帖为 @{source['actor']} · {source['semantic']} · "
            f"{timing} {duration(lead)}"
        )
    return f"叙事源审计：{origins[audit['origin_resolution']]}；{exact}。"


def duration(seconds):
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3_600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    hours, remainder = divmod(seconds, 3_600)
    return f"{hours}h{remainder // 60:02d}m"


def _percent(value):
    return "n/a" if value is None else f"{float(value) * 100:.1f}%"
