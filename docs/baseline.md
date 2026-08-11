# 实时纸面交易 baseline 定义

这个 baseline 的用途是建立一个可重复、可审计的实盘数据基准，而不是证明或承诺策略能够盈利。所有 BUY、标记和 1 小时结果都必须保留来源时间、证据 URI、区块信息和运行 manifest；缺失数据时应失败关闭，不得补造有利数值。

v6 的策略身份是 `flow-v6-debot-kol-history-onchain-quorum-atomic-fdv`。它明确设置 `official_signal_only = true`、`use_dex_market_gate = false`：DeBot 官方 SmartMoney/KOL 信号是唯一能够触发 BUY 流程的来源，DEX 数据只做独立的漏币审计。

## DeBot-only 信号与 KOL 历史门

生产路径直接轮询 DeBot 官方 HTTPS API，并复用已有登录 Cookie；浏览器或 CDP 不是信号采集、决策或下单依赖。PairCreated、DexScreener discovery、DEX 过去 1 小时涨幅 Top100，以及其他观察来源都不能创建、升级或解锁 BUY 候选，也不能参与 BUY 评分或市场门槛。

每条 SmartMoney BUY 信号必须在决策截止时间之前，已经有同一 token 的合格 DeBot 官方 KOL BUY 证据。未来才出现的 KOL 证据不能倒灌解锁当前 SmartMoney 信号。当前这条信号本身如果就是合格的 KOL BUY，则可以作为自己的 KOL BUY 证据，不要求再找到更早的第二条 KOL 信号。该证据会持久化，重启后仍可用于后续 SmartMoney 信号，但必须保留原始 signal identity、provider event time、可用时间和资格判定时间。

准备 BUY 时与提交 BUY 前都要复核官方信号。signal ID/不可变身份不匹配、provider event time 或抓取可用时间超过新鲜度上限、信号已经失效或被替换、安全字段缺失、蜜罐状态未知、税率无法解析或超过上限，全部拒绝；不能用旧 signal cache 或后来的相似信号补位。

DEX Top100 的唯一职责是做事后覆盖审计：将每个榜单 token 标成 `COVERED`、`MISSED` 或 `UNKNOWN`，帮助判断 DeBot-only 系统漏掉了什么。`MISSED` 只是一条研究证据，绝不能自动补发 BUY，DEX 排名、1h 涨幅和 DexScreener MC 也绝不能影响 BUY 决策。

## BUY 决策边界与两个估值口径

只有通过上述 DeBot 官方信号与 KOL 历史门的候选才能进入执行边界。DeBot payload 中的 MC、流动性和活跃度只保留为信号证据，不是 BUY MC；DexScreener 快照和 DEX 排名不再承担资格门或执行门。

一旦系统决定 BUY，必须重新取得当时最新的 canonical execution block，并在该区块上完成精确成交报价和 FDV 探针；不能拿采集器最近一次缓存的 MC，更不能把 30 秒前的 MC 写成 BUY MC。纸面 BUY 的耐久估值锚点来自 PancakeSwap V2 的同执行块链上探针：在精确成交报价的 block 上读取 `totalSupply/decimals`，用不超过总供应量百万分之一的 token 沿已验证 BUY path 的精确反向 route 做卖出报价，再缩放为 `fee_adjusted_spot_fdv_usd`。它与成交报价具有相同 block number/hash/timestamp、RPC host 和 route identity，并保存全部 raw integer evidence。这个值是 total-supply FDV，不是 circulating market cap；数据库中的历史字段名 `buy_market_cap_usd` 为兼容保留，运行 source/metadata 会明确标成 execution-block FDV。

提交前官方信号复核、执行报价或同块估值任一缺失、过期、来自未来、区块不一致、超过允许的时间偏差或策略复核失败，都不记录 BUY。系统不会用最后一次采集器缓存补值。

每个入场或持仓标记整包开始时，都会并发探测配置中的两个独立 BSC RPC：Blast 与 publicnode；每个 endpoint 的请求超时为 4 秒。两端都必须返回 chain ID 56 且区块足够新鲜：探测时 block age 不超过 3 秒、未来偏差不超过 2 秒、有效高度差不超过 2 个块，同高度若返回不同 hash 则失败关闭。这里是 soft quorum，并不要求两端始终处在同一高度，也不代表链上最终性确认。系统从有效结果中选最高高度、同高度再选 RTT 最低者，随后把该整包的合约读取固定到胜出 endpoint；phase 2/3 中不允许透明 failover。整包最后观察时间不得早于 head 探测时间，且相对区块时间的 age 必须不超过 4 秒。少于两个有效节点、quorum 分叉、执行中节点切换或 head 过期都不产生 BUY/mark。

## 纸面成交和持仓标记

BUY 的纸面成交边界使用官方 PancakeSwap V2 Router 的 exact-input 路由报价。BUY path 来自链上 Pancake V2 route 解析与验证，而不是 DEX 榜单或 DexScreener pair 选择；反向清算必须严格使用 BUY path 的逆序。系统在同一 canonical block 上读取 factory/token0/token1，并用官方 factory 的 `getPair` 验证每一跳，随后固化 `route_id`、所有 hop pair 和正反向 path。非 Pancake venue（包括 Flap.sh）、明确的 V3 pair、pair/factory 不一致或自定义路由都会失败关闭，不记录 BUY。

同一执行块中，系统先对固定原始 USDT 数量做 BUY exact quote，再对实际得到的精确原始 token 数量做反向 exact liquidation quote，同时完成 total-supply FDV 探针。BUY、roundtrip、route proof 和 FDV 必须全部成功并具有相同 block number/hash、RPC host 与 route identity；否则整个 entry bundle 作废。roundtrip 只度量 Router 报价中包含的 AMM 池费和当块储备价格冲击。

持仓数量固定为 BUY 报价得到的原始 token 数量。当前 `mark_refresh_seconds = 0.5` 的准确含义是：对每个 BUY，距离该 BUY 上次提交 mark 任务至少 0.5 秒、且没有该 BUY 的未完成任务时，才允许再次提交。它不是“每 0.5 秒必定生成一个样本”的承诺。实际 mark 频率还受主循环、可用 worker、RPC 往返时间、失败重试，以及 BSC 是否已经产生新的 canonical block 限制。

每次 mark 任务执行严格的三阶段 all-or-nothing bundle：先完成双 RPC fresh-head quorum 并固定胜出 endpoint；再在 BUY 时固化的反向 route 上批量读取所需 decimals、`totalSupply` 和精确持仓 liquidation；最后在同一 block hash、同一 host、同一 route 上完成微量 FDV probe。任一阶段失败都不返回 partial bundle，因此即使 liquidation 已在 phase 2 得到结果，只要 phase 3 的 FDV 失败也不会保存这条 liquidation mark。

区块身份使用 `(block_number, block_hash)`。完整 bundle 成功后，runtime 和 SQLite 才检查该 BUY 是否已经存在相同 hash 的 durable mark；重复块不会被写成多个独立样本，但当前实现仍可能为同一 BSC block 执行完整 RPC bundle。清算 mark 与 FDV observation 在同一个 SQLite transaction 中提交；任何冲突或写入失败会一起回滚，避免只留下半个样本。

## Canonical block 与重组处理

报价源通过双 RPC quorum 选择并保存 block number/hash/timestamp，随后只在胜出 endpoint 上对 router、factory、pair、`decimals` 和 `totalSupply` 等合约读取使用 EIP-1898 `blockHash` selector，并要求 `requireCanonical = true`。若胜出节点不知道该 hash、认为它已非 canonical、返回不同 fork，或不支持这个 selector，当前报价/估值会失败关闭；整包内部不会切换到备用 endpoint，也不会退回仅按 block number 查询或把两个 fork 的状态拼成一个样本。

同高度出现新 hash 时，它是新的区块身份，必须重新报价和验证；旧 hash 若因 reorg 不再 canonical，后续 EIP-1898 读取会失败，而不是静默沿用旧 fork 的数值。这个机制减少跨 RPC、跨 fork 混值，但不会消除链上最终性风险。

## 1 小时结果

评价窗口从 BUY 时间到 `BUY + 1h`（含）。BUY 边界本身只作为不可变起点；只有时间严格晚于 BUY 的真实观察才计入买后样本数。输出至少包括：

- BUY 时同执行块 FDV，以及第二次 provider market cap 旁证；
- 窗口内实际观察到的最高同块 FDV（1h peak）及发生时间；
- `FDV multiple = 1h peak FDV / BUY execution-block FDV`；
- 窗口末最后一个合格观察值及其 multiple；
- peak paper PnL 与 1h paper PnL；
- 观察数、最后观察时间和最大采样间隔，用来暴露漏采，而不是把漏采区间当作没有波动。

最高 FDV 至少以不可变的 BUY FDV 为起点。没有真实买后观察时不结算 1 小时结果；任一采样间隔超过配置上限（当前 20 秒）也不纳入胜率或收益统计。不得插值、回看后补点或宣称未观察到的峰值。

direct liquidation 报告使用同样严格但独立的覆盖门槛：从 BUY 边界到第一条清算 mark、相邻 mark 之间、以及最后一条 mark 到 `BUY + 1h` 的所有间隔都必须不超过上限。成熟仓位只要首段、段间或末段任一处超限，就标记为 `coverage_incomplete`，排除在 direct peak/1h PnL、胜率和汇总之外；例如只有 `BUY + 10m` 一条 mark 时，绝不能把它冒充 1 小时收盘。漏采期间已有的 mark 只保留在 `observed_*` / `latest_sample_*` 诊断字段中。

盈利判断以每次“精确持仓清算 USDT − 原始 10 USDT 投入”的 direct liquidation paper PnL 为主；这是当前唯一以固定真实持仓数量和 exact liquidation quote 计算的可执行纸面收益口径。它不读取或缩放 FDV。`fee_adjusted_spot_fdv_usd` 使用 ERC-20 total supply，因此 FDV ≠ circulating market cap；FDV multiple 及其推导的 peak/1h paper PnL 只能作为独立估值曲线指标，不能与 direct PnL 混算，也不能冒充可执行收益。

即使 direct liquidation paper PnL 为正，它仍未计 transfer tax、gas、MEV、交易广播后的滑点和真实卖出失败，所以只是纸面可执行报价，不是已实现利润，也不能据此声称系统能够盈利。

## 当前刷新节奏

- 主调度 tick：0.25 秒；
- DeBot 官方 SmartMoney/KOL 信号：3 秒；
- DeBot completing/completed 与 Pancake V2 `PairCreated` 即使继续采集，也只作为观测/审计输入，不能触发 v6 BUY；
- DEX/DexScreener 排名审计：30 秒，完全独立于 BUY；
- DeBot 官方候选复核：1 秒；
- 持仓 mark：每个 BUY 最快每 0.5 秒提交一次，实际新样本频率受 RPC 延迟和新区块产生速度限制，并按 canonical `(number, hash)` 去重。

网络请求不持有全局发现锁，各 DeBot 请求彼此独立。刷新速度只决定信号多久能被看见；真正的 BUY MC/FDV 始终在 BUY 决策发生后重新取得最新 canonical execution block 并现场计算，不能复用任何轮询周期里的缓存估值。

## 本地只读看板

看板只读取当前 strategy scope 的本地 SQLite 与 state，不创建网络 client、不会发单，也不提供写接口。v6 看板中的 DEX Top100、`COVERED/MISSED/UNKNOWN` 和 1h 涨幅排名都是漏币审计视图，不能被解释成交易触发器：

```bash
PYTHONPATH=/home/john/debot4/src python -m debot4.baseline.cli --root /home/john/debot4 --config conf/baseline-v6.toml dashboard --port 8766
```

浏览器打开 `http://127.0.0.1:8766/`。页面每 2 秒刷新一次，但这只是显示频率，不会改变上面的信号轮询、候选复核或持仓 mark 节奏。每次 HTTP 刷新使用一个一致的 SQLite 只读 snapshot，响应只包含页面所需的有界汇总、最近 200 笔 BUY 明细、清洗后的最近 5 条错误和来源成功时间，不返回完整 state、manifest 或全量 position 报表。

顶部绿色状态要求 SQLite 可读且 state heartbeat 在 15 秒内；账本可读但心跳缺失、来自未来或过期时会明确显示运行异常/暂停。FDV 仍是不可执行的 total-supply 估值，direct liquidation PnL 仍是未计 transfer tax、gas、MEV、成交后滑点和真实卖出失败的纸面报价。没有真实 BUY，或尚无覆盖合格的完整 1 小时样本时，看板不能用于判断策略是否盈利。

## 运行健康、状态和重启恢复

`health` 是无网络、只读、只检查当前 strategy scope 的本地健康门。它会读取 state JSON，并以 SQLite URI `mode=ro`、`PRAGMA query_only=ON` 打开当前 scoped ledger，验证必需 schema、开放 BUY 及其最新 liquidation mark 的新鲜度；它不会创建数据库、迁移 schema、写入 ledger，或为了“修复”状态发网络请求。数据库缺失、不可读、schema 无效，或开放 BUY 的 mark 超过配置的 observation-gap 上限，都会硬失败。

默认 state JSON `updated_at` 上限为 15 秒；状态缺失、JSON/时间格式无效、时间来自未来超过 3 秒容忍度或 state 超时都会硬失败。PairCreated 或 DEX 审计断流只能形成结构化 warning，不能改变 DeBot 官方信号的 BUY 资格；DeBot 官方信号源断流、过期或复核失败则必须失败关闭。辅助 JSONL audit log 写入异常同样只报告 warning，因为 SQLite 才是权威 ledger；mark pipeline 和 scoped ledger 异常仍是硬失败。

state v3 保存 `source_last_success_at`，分别记录 DEX 审计、PairCreated、DeBot 官方信号、两个 DeBot stage 和兼容 supplemental path 最近一次成功完成的时间。成功但没有候选的 poll 仍可刷新对应成功时间；失败不会刷新。各来源不得用笼统的 `last_discovery_at` 或其他来源的成功互相掩盖；DEX 审计健康只代表漏币审计覆盖，不代表 BUY 信号健康。

重启时，候选池从 state v3 的完整 `candidate_seeds` 恢复，包括发现来源、证据、event key、pair/quote token、首次/末次发现及尝试节奏；token-only 列表只为旧工具保留，不作为恢复依据。开放 BUY 和 mark 去重状态以 SQLite 为准：系统读取每个开放 BUY 的最新 durable liquidation mark；若还没有 mark，则从 BUY 的 entry metadata 恢复执行块 `(number, hash)`。因此进程重启不会把内存清空误当成一个新观察窗口，也不会重复记录 BUY 所在区块。

v6 当前策略版本为 `flow-v6-debot-kol-history-onchain-quorum-atomic-fdv`。配置会将它转换为稳定、带完整 SHA-256 的 strategy scope，SQLite、state、JSONL 和 manifest 全部位于该 scope 下；同版本重启继续同一组 artifacts，任何版本变化都会进入新 scope，不能与旧 baseline 混写。

## 审计日志边界

运行 JSONL 按大小轮转：默认每个文件最多 8 MiB，保留 active file 加 7 个编号备份，名义上限 64 MiB。`paper_buy`、mark、outcome 和 error 等事实事件不会做重复聚合；单条事件若超过文件上限，会保留事件类型、关键身份字段、原始字节数和 SHA-256，而不是无限写入超大 provider payload。

`entry_rejected` 为避免高频拒绝淹没审计盘，按高层 `(status, reason)` 聚合：每组第一条完整写入，后续重复默认累计到 64 条或 15 秒时写 `entry_rejected_summary`，并包含策略原因、发现类型、来源计数和有限 token 样例。聚合只压缩重复拒绝，不得延迟、覆盖或代替 BUY/error 等事实事件。JSONL 是有界运行审计，不替代 SQLite 中的 durable ledger。

## 明确未覆盖的执行风险

当前 baseline 没有覆盖：

- token transfer tax / fee-on-transfer 机制；
- gas、priority fee 或失败交易成本；
- MEV、sandwich 与观察后滑点；
- 真实 sellability，包括 honeypot、动态黑名单、额度限制，以及 `eth_call` 成功但真实交易失败的情况。
- Flap.sh 等非 Pancake venue、custom-router path，以及 Pancake V2 flash-swap callback 交易；这些候选不会被当作已支持的 BUY 路径。

因此，DeBot provider MC、链上 FDV、Pancake V2 router quote、1h peak、multiple 和 direct liquidation paper PnL 都只能用于比较和筛选实验；DEX 排名只用于漏币审计。至少要有一笔由真实 DeBot 官方信号触发并实际写入 ledger 的 paper BUY，而且该 BUY 已完成覆盖合格的完整 1 小时窗口，才允许报告这笔样本的结果。在这之前不得宣称系统盈利；即使之后样本为正，也不得将纸面报价描述为实盘已成交利润，或声称、承诺、保证策略能够盈利。

## Run manifest

每个 `strategy_version` 映射到独立、稳定且带完整 SHA-256 的 artifact scope；SQLite、state、JSONL 和 manifest 不会与其他策略版本混用。同版本服务重启会继续同一条 baseline，版本变化会建立新 scope。

启动边界生成的 JSON manifest 记录 UTC `started_at`、strategy version/scope、实际 artifact 路径、配置文件 SHA-256、当时 `src/debot4/baseline/` 与 `src/debot4/narrative/` 下全部递归 Python 文件的逐文件 SHA-256、Python executable/version/implementation、上述 source definitions 和 honest limitations。它还显式哈希 baseline 生产路径直接依赖的最小外部代码集合：`core/events.py`、`features/narrative.py`，以及白名单中的 DeBot、signal context、FxTwitter、DEX、HTTP、BSC RPC 和 Pancake source 模块；不会为了方便递归哈希整个仓库或整个 `sources/` 包，也不会读取外部 cookie 文件或凭据存储。配置只按原始字节计算哈希，绝不复制配置值，因此 manifest 不得包含 cookie、API key 或其他凭据。

同一 strategy scope 的 manifest 是不可变实验身份。第一次启动会先完整写入并 `fsync` 临时 inode，再以“不覆盖已存在目标”的原子方式发布。以后重启会在打开 SQLite、构造网络 client 之前重新构建当前 manifest；除 `started_at` 外，配置哈希、全部代码哈希、strategy version/scope、artifact 路径、Python 身份、source definitions 及其他 manifest 字段必须完全一致。一致时保留原文件和原始 `started_at`，绝不覆盖；任一依赖、配置或语义变化，或现有 manifest 损坏，都会失败关闭，且只报告发生变化的字段名与身份 SHA-256，不输出配置内容。

单实例锁冲突退出码为 4，manifest 身份/格式失败退出码为 7，两者互不混淆。systemd 将配置错误 3、锁冲突 4 和 manifest 错误 7 都列入 `RestartPreventExitStatus`，避免永久错误造成无限重启。任何会影响策略、采样、数据来源或会计语义的修改，都必须在启动前提升 `strategy_version`，进入新的空 scope；不得删除或覆盖旧 manifest 来强行续跑。
