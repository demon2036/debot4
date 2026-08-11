"""Evidence-focused prompts for active and passive narrative investigation."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Mapping


SYSTEM = """你是 meme 叙事取证搜索员，不是喊单员。只报告可给出完整 URL、账号、帖子 ID、绝对 UTC 时间的公开证据。严格区分原始事件、首次出现 exact CA、传播放大和价格启动后的复盘。原帖没有 CA 就只能叫叙事源，不能叫代币背书。找不到写 unknown，禁止补写链接。事实、推断、反证、未知项必须分开。禁止输出分数、BUY/SELL、仓位、入场价或目标价。"""

FORMAT_REPAIR_SYSTEM = """你是严格 JSON 格式化器。只能摘录、压缩和重排用户提供的原回答，不能搜索、补充、推断或新增事实，不能增加原回答中没有的 URL、CA、人物、时间和结论。枚举映射只是格式归一化，不算新增事实；无法映射必须写 unknown。缺失字段用 unknown、空数组或 null。不得原样回显空 schema；只输出一个 JSON 对象。"""

_ENUMS = """
枚举只能取以下值：
- event_role: source|catalyst|amplification|counter|unknown
- phase: latent|discovery|validation|expansion|saturation|decay|revival|unknown
- catalyst_type: source_event|official_adoption|creator_action|ecosystem_actor_action|kol_amplification|community_remix|market_anomaly|old_narrative_revival|no_public_catalyst|unknown
- ca_carrier_status: no_ca|single_candidate|open_race|leaders_aligned|leaders_split|contradicted|unknown
"""

_SEARCH_FIELDS = """取证正文必须逐项覆盖：narrative_key、one_line_meme、event_role、narrative_source_summary、why_now、propagation_engine、future_24h_path、ca_carrier_status、competing_cas、narrative_leader、market_leader、phase、catalyst_type、counter_evidence、invalidation_conditions、evidence_urls、unknowns。"""

_JSON_FORMAT = """
只输出一个完整、可解析的 JSON 对象，不要输出 Markdown 或额外文字：
{
  "narrative_key":"",
  "one_line_meme":"",
  "event_role":"unknown",
  "narrative_source_summary":"",
  "why_now":"",
  "propagation_engine":[],
  "future_24h_path":[],
  "ca_carrier_status":"unknown",
  "competing_cas":[],
  "narrative_leader":null,
  "market_leader":null,
  "phase":"unknown",
  "catalyst_type":"unknown",
  "counter_evidence":[],
  "invalidation_conditions":[],
  "evidence_urls":[],
  "unknowns":[]
}
所有 CA 对象必须且只能包含 chain、address、symbol 三个键；address 必须是原回答中完整、非空的 exact CA。BSC/EVM address 必须是 0x 加 40 个十六进制字符；Solana address 也必须完整非空。无法组成合法 CA 对象时，从 competing_cas 删除该项，并把 narrative_leader 或 market_leader 设为 null。narrative_leader 和 market_leader 只能表示代币 CA，绝不能填账号、URL 或帖子；前者按叙事源头归属选，后者按当前真实传播与流动性收敛选。没有已核验 exact CA 时数组必须为空、leader 必须为 null。narrative_key 必须能在原回答列出的已核验原文里直接找到，不能从上涨反推或发明。
"""

_TEMPLATE_ECHO_MARKERS = (
    "已核验原文中真实出现的最短叙事实体",
    "普通人一句话就能复述的 meme",
    "谁在什么绝对时间做了什么",
    "此刻相对旧闻新增了什么",
    "具体说明谁会把什么内容传给下一群人以及原因",
    "未来 24h 可观察的下一传播节点或失败分支",
    "足以削弱因果链或 CA 归属的事实",
    "未来出现什么可验证事实会推翻当前叙事",
)


def format_repair_prompt(raw_answer: str) -> str:
    """Request schema repair without granting authority to add evidence."""

    bounded = raw_answer.strip()[:50_000]
    return f"""把下面原回答逐字段整理成指定 JSON。允许忠实摘录和压缩原回答，但不得搜索、不得新增或纠正事实；原回答没有的证据链接必须保持缺失。narrative_key 和 one_line_meme 必须从原回答提取为非空字符串；若原回答明确无法建立公开叙事，两者都写字面值 unknown。不得原样返回空 schema。只输出 JSON。
{_ENUMS}{_JSON_FORMAT}

原回答开始：
{bounded}
原回答结束。"""


def contains_template_echo(text: str) -> bool:
    """Reject schema examples copied as alleged findings."""

    return any(marker in text for marker in _TEMPLATE_ECHO_MARKERS)


def proactive_investigation_prompt(
    *,
    actor: str,
    event_text: str,
    event_at: datetime,
    event_url: str = "",
    chain: str = "BSC",
    actor_context: Mapping[str, object] | None = None,
    post_type: str = "post",
    target_author: str = "",
    target_text: str = "",
) -> str:
    context = json.dumps(
        dict(actor_context or {}), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    )
    return f"""主动人物事件调查
人物/组织: {actor}
系统核验身份上下文: {context}
事件 UTC: {event_at.isoformat()}
已核验事件 URL: {event_url or "unknown"}
事件类型: {post_type}
原文/事件: {event_text}
被回复/引用账号: {target_author or "unknown"}
被回复/引用内容: {target_text or "unknown"}
目标链: {chain}

搜索并重建：
1. 原始帖子及上下文，独立核验回复/引用对象，并判断动作类型；
2. 叙事源头、why now、一句话 meme，以及真实传播发动机；
3. 最多列 3 个未来 24h 传播节点和对应停滞信号；
4. 最多列 3 个已有直接证据的竞争 CA；每个必须给 exact CA 与首个 exact-CA 公开帖，否则不要列；
5. 有证据才区分 narrative leader 与 market leader，没有就保留 null；
6. 最多列 3 条最关键反证或失效条件。
这是实时初筛，不做百科式历史综述。最多使用 4 个 X status URL；先回答当前事件是否产生了新的、可验证的叙事变化。深度回溯交给后续独立任务。
原帖没有 CA 时只能认定为叙事源，绝不能写成对任一代币的背书。不要用 KOL 数量给叙事打分。
身份权限只能来自“系统核验身份上下文”的 capabilities；propagation_kol 只能提供传播线索，不能建立官方源头、官方采用或 CA 绑定。自称身份、互动量和历史喊中过均不能扩大权限。
{_SEARCH_FIELDS}
输出简洁取证正文；每个事实紧邻完整 X status URL。不要输出 JSON，结构化由独立无搜索步骤完成。"""


def passive_investigation_prompt(
    *, token_address: str, anomaly: str, observed_at: datetime, chain: str = "BSC"
) -> str:
    return f"""被动市场异动溯源
链: {chain}
exact CA: {token_address}
异动 UTC: {observed_at.isoformat()}
异动描述: {anomaly}

从异动时间向前搜索，重建：
1. 最早真实事件或文化母体；若没有公开催化，明确写 unknown；
2. 合约创建、首个 exact-CA 帖、首个 DeBot/钱包动作、价格启动、后续大账号放大的绝对时间线；
3. 这是新事件、老叙事新催化、纯喊单/私域资金，还是无公开催化；
4. why now、传播发动机、未来 24h 的具体传播节点与停止条件；
5. 同叙事所有竞争 CA、narrative leader 与 market leader；
6. 帖子属于 pre-pump、during-pump 还是 post-pump，禁止把后发帖倒灌成原因；
7. 老币套牢、错误 CA、复制币、洗量、否认和其他反证、失效条件。
这是实时初筛：最多使用 4 个 X status URL、3 个竞争 CA 和 3 个传播节点。无法在本轮直接核验的内容写 unknown，交给后续深度回溯。
不要因价格上涨反向编造故事，也不要把市场异动本身当作叙事证据。
{_SEARCH_FIELDS}
输出简洁取证正文；每个事实紧邻完整 X status URL。不要输出 JSON，结构化由独立无搜索步骤完成。"""
