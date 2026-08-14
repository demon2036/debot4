# BSC 金狗 13 标的 / 32 波逐波归因（2026-08-06—2026-08-13 UTC）

> 结论先行：本报告只把首个精确交易达到回放基线 `1.02x` 之前的机器可观测事件称为“提前”。时间领先不等于因果，更不等于可买。

## 第一性原理结论

```text
32 个胜者波段
├── 21 波：至少一条经语义复核公开信号早于 +2%
├── 6 波：公开面为空，但前一区块资金可在确认后看到
└── 5 波：首动与 +2% 同块，只能靠待打包流/Builder 理论看见
```

公开覆盖 21 波的最近一条信号提前量（避免把数日前旧帖冒充临拉爆点）：

```text
<1m 1 ｜ 1–5m 1 ｜ 5–30m 4 ｜ 30m–6h 10 ｜ 6–24h 2 ｜ ≥24h 3
```

因此，普通确认流零延迟理论上限是 **27/32**，5 秒延迟是 **24/32**；只有理想化零延迟 pending/Builder 全覆盖才达到 **32/32 原始事件可见**。这不是 32/32 可盈利预测：当前点时合格 KOL/聪明钱包仍为 **0**。

`fresh/standing` 只保留为 replay 状态字段：后续波以此前有效波 reset 分界，首波以创建时间分界。它不等于“临拉新爆点”；是否接近启动请以最近提前秒数和逐波人工判断为准。

叙事源审计：13 个项目中，`4` 个有可直验上游题材源，`12` 个能定位首个有意义 Exact-CA 公开帖；但创建前已有有意义 Exact-CA 帖的是 **0/13**。

## 固定口径

- 窗口：`2026-08-06 00:00:00 ≤ t < 2026-08-13 00:00:00 UTC`。
- 有效波：从局部低点至少 `2x`，5 分钟 close 峰值 FDV 代理至少 `$500K`，回撤 `60%` 后重置。
- 最高值：`5m high × 当前 supply` 的固定窗口 FDV 代理，不是可成交市值。
- 逐笔价格：从基线建立扫描至 `2x` 突破 K 线结束后 60 秒；若 1m OHLC high 与逐笔成交分歧，两者并列并把差异记为反证。
- 头像/banner：CDN 资源时间只作线索，永不单独作为 UI 换图或因果证明。
- KOL：scanner、recap、relay、reply、钓鱼和峰后喊话不算提前 KOL；钱包 provider 标签也不等于历史技能合格。

## 标的总览

| 标的 | Exact CA | 窗口最高 FDV 代理 | 波段 |
|---|---|---:|---:|
| CETS | `0xb0c2ab5af4028461ace3f6e1c33a4ee1404e7777` | $6.982M | 5 |
| Asian games | `0x31d19b3633ebdb60dc9d690b3e9eb1fff61a7777` | $5.325M | 1 |
| bStocks | `0x244b112cf746e62a5df723cbde9906a6defd7777` | $4.223M | 2 |
| BOT | `0xbcad9b1b85af1cd81437252bf50b87235c0b7777` | $2.298M | 2 |
| fourclub | `0x530227c569960ba0fa345f19cf743a477f147777` | $1.677M | 4 |
| bNS | `0xdc5e4d5f157482059126eb15d84f2ff9368b7777` | $1.632M | 3 |
| 月薪喵 | `0xc73e1b136c576d1429cb84522a8c35c81d9d7777` | $1.275M | 3 |
| TKM | `0x86a5a545a5d9f7ee14afecb7e62b7ae7bab27777` | $1.109M | 1 |
| Racoonzilla | `0x12d5a0c58ef299bedd309ec4964ffa3145827777` | $1.072M | 1 |
| XchangetheWorld | `0xe9d476ce8ba9431a6c1ae39c00e84dab5c717777` | $1.048M | 2 |
| CSI | `0x2f31614f7a8bb702f7898d379b3c23db73b87777` | $1.009M | 3 |
| SpaceXcoin | `0xf225e70162837a811c77dc2bb413a5c06e97ffff` | $962.8K | 3 |
| 币安城 | `0x9ecfbb6c0ce91d5ac00e1f7378880523cb8d7777` | $897.0K | 2 |

## 提前账号 / 频道线索（不是合格 KOL）

以下只证明该公开来源曾早于交易级 +2% 出现。`总覆盖波` 可重复来自同一标的后续波；没有失败样本精度、稳定身份和钱包控制证明，因此全部仍是 discovery lead。

| 来源 | 账号/频道 | 总覆盖波 | 新鲜覆盖波 | 跨标的 | 最近提前 | 直接证据 |
|---|---|---:|---:|---:|---:|---|
| x_independent | `ROME9998` | 3 | 1 | 1 | 28m52s | [最近回执](https://x.com/ROME9998/status/2086744159382372690) |
| x_independent | `ojkared8139` | 3 | 1 | 1 | 9h57m | [最近回执](https://x.com/ojkared8139/status/2085656949635645872) |
| x_independent | `Will_binance` | 2 | 1 | 1 | 17h14m | [最近回执](https://x.com/Will_binance/status/2086092743408071070) |
| x_independent | `zygfrids` | 1 | 0 | 1 | 1h47m | [最近回执](https://x.com/ZygfridS/status/2087201834821976274) |
| telegram_independent | `zygfridjournal` | 1 | 0 | 1 | 1h52m | [最近回执](https://t.me/zygfridjournal/1997) |
| x_independent | `SpeedevsO` | 1 | 0 | 1 | 2h03m | [最近回执](https://x.com/SpeedevsO/status/2086543928061284777) |
| x_independent | `false2z` | 1 | 0 | 1 | 2h12m | [最近回执](https://x.com/false2z/status/2086541464171860432) |
| x_independent | `oxxiaoqi` | 1 | 0 | 1 | 4h25m | [最近回执](https://x.com/Oxxiaoqi/status/2086365449709896107) |
| x_independent | `zhuilong888` | 1 | 0 | 1 | 4h48m | [最近回执](https://x.com/zhuilong888/status/2086359629999776017) |
| x_independent | `guduchaobi1015` | 1 | 0 | 1 | 5h07m | [最近回执](https://x.com/guduchaobi1015/status/2086354878222463331) |
| telegram_independent | `ch1ro0` | 1 | 0 | 1 | 6h16m | [最近回执](https://t.me/ch1ro0/7501) |
| x_independent | `layla030906` | 1 | 0 | 1 | 7h30m | [最近回执](https://x.com/layla030906/status/2086799756614041739) |
| x_independent | `monkeyd_long` | 1 | 1 | 1 | 48h33m | [最近回执](https://x.com/monkeyd_long/status/2086139789095641395) |
| x_independent | `moneymancalls` | 1 | 0 | 1 | 77h57m | [最近回执](https://x.com/moneymancalls/status/2085695771261739426) |
| x_independent | `feibo03` | 1 | 0 | 1 | 80h56m | [最近回执](https://x.com/feibo03/status/2085650699095023692) |

结论：独立账号/频道候选 **15** 个；正式新 KOL **0**。按本波新鲜信号重复覆盖至少两波的候选 **0** 个，跨两个标的的候选 **0** 个。总覆盖多波若只是同币旧帖站岗，不能当作连续预测。

## 钱包点时技能审计（不是聪明钱包名单）

从 26 个历史 X-attributed 候选中，只有 8 个进入完整失败样本审计。在信号发生前已成熟的 164 个 24h 钱包×代币结果中，163 个可测、12 个命中，但没有一个达到最低技能门槛。

| 当前 X 绑定 | 钱包 | 点时可测样本 | 命中 | 命中率 | 技能门禁 |
|---|---|---:|---:|---:|---|
| `lyleeewmc` | `0x108ad3125bae57daa6d72bd9f2060e07841889c2` | 16 | 0 | 0.0% | FAIL |
| `wanger2gou` | `0x1e115fb1f7135397d32e901d893bdf0441356c10` | 20 | 1 | 5.0% | FAIL |
| `Tothejpg` | `0x379dd75fd82daa5ae5f795e8c550eef57190c9fa` | 32 | 1 | 3.1% | FAIL |
| `AceCzarG` | `0x6c5e56c80e8a11a38f709c43c8aea2219bf98236` | 11 | 1 | 9.1% | FAIL |
| `c_cloudplayer` | `0x7730b1bf8a21ce829b83e1a0f360fad61d6643e4` | 22 | 1 | 4.5% | FAIL |
| `AkiGoa978977` | `0x87257e9ee9c6d95877db536c37bb606d0d96faa4` | 13 | 2 | 15.4% | FAIL |
| `lxkk__` | `0xbb93a804432917f3bfbc5a63c331d8e89c43731b` | 0 | 0 | n/a | FAIL |
| `xxxxliuqilin` | `0xf5c2b8a1553052a9f5d47023e4cddfa51a11405c` | 49 | 6 | 12.2% | FAIL |

门槛是至少 10 个点时成熟且可测样本、24h 内同时达到 `2x` 与 `$500K FDV` 的命中率至少 20%。这些 X 绑定本身仍是当前快照，不足以证明历史时点控制关系。

## CETS

### 波 1 — 至少一条经复核公开信号早于 +2%

行情：`08-09 14:50 UTC` 低点 → `08-10 06:55 UTC` 峰值，`10.67x`，峰值 close-FDV $528.6K；首个交易级 +2% `08-09 15:01 UTC`；1m +20% 边界 `08-09 15:10 UTC candle（严格提前截止 08-09 15:10 UTC）`。

```text
最早叙事源 ─ @cetsongold 在 08-06 发布上线、Exact CA 与 Tokenomics，是当前最早可核验项目源，早于首个有效大波数天。
├── 官号/头像 ─ 头像/banner 资源时间只证明当前资源线索；项目官号持续发帖才是可用证据。
├── +2% 前信号 ─ 官号 12:08 的“Back to basics. $CETS”早于交易级 +2% 2h53m48s，可在线发现；因官号高频发帖且无独立确认，不能把单帖认定为点火。
├── 链上点火 ─ +20% 前观测 7 笔、约 $749；没有过滤后标记聪明钱拉升买入。
├── 上升传播 ─ 本波上升中官号连续运营，外部 TG 接力主要在后续波段增强。
└── 峰后内容 ─ 官号仍持续发帖，单一峰后复盘不足以切分每次贡献。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @cetsongold · project_announcement · 创建后 3m08s。

证据计数：公开提前 `fresh=4` / `standing=0` / 最近提前 `2h53m`；+20% 前观测流 `7 买 / $749 / 4 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=0/$0`。

最佳支持机制：**项目运营 + 市场资金流**；置信度：**中低**。

反证：没有首波启动前 30 分钟的新鲜公开事件；缺少已验证聪明钱包。

未知项：真正点火买家身份；首波前 TG/私群动员是否完整。

可直连证据（完整回执见 JSONL 账本）：

- [x_project · closest-public-before-1.02/2h53m · 2026-08-09T12:08:04Z](https://x.com/i/status/2086424268783624632)
- [cetsongold · historical_baseline/banner_resource_timestamp · 2026-08-06T01:12:45Z](https://api.fxtwitter.com/cetsongold)
- [cetsongold · historical_baseline/project_announcement · 2026-08-06T02:59:34Z](https://x.com/cetsongold/status/2085199072928186463)
- [vutnerable · historical_baseline/market_thesis · 2026-08-06T03:03:23Z](https://x.com/vutnerable/status/2085200032832356537)
- [cetsongold · historical_baseline/project_announcement · 2026-08-06T03:14:56Z](https://x.com/cetsongold/status/2085202940441325620)
- [cetsongold · historical_baseline/post · 2026-08-06T03:38:30Z](https://x.com/cetsongold/status/2085208867819151399)
- [cetsongold · historical_baseline/post · 2026-08-06T04:07:37Z](https://x.com/cetsongold/status/2085216196190966204)
- [cetsongold · historical_baseline/post · 2026-08-06T04:27:06Z](https://x.com/cetsongold/status/2085221098388644291)

### 波 2 — 至少一条经复核公开信号早于 +2%

行情：`08-10 16:30 UTC` 低点 → `08-10 19:30 UTC` 峰值，`7.25x`，峰值 close-FDV $1.744M；首个交易级 +2% `08-10 16:44 UTC`；1m +20% 边界 `08-10 17:08 UTC candle（严格提前截止 08-10 17:08 UTC）`。

```text
最早叙事源 ─ 项目上线/Tokenomics 已长期公开，是背景条件；本波前官号延续 CETS 运营。
├── 官号/头像 ─ 官号“The green came to me”早于 +2% 约 2h39m；“Trust me”在 +2% 后，后者只能算上升放大。
├── +2% 前信号 ─ 新增复核官号状态在本波 +2% 前可在线发现，但它是项目自推、不是独立 KOL 认可，也无法从时间领先单独证明点火。
├── 链上点火 ─ 逐笔 provider 重放在 +20% 首跨越前有 27 笔买入、约 $2,338、6 个钱包，其中 4 个重复买、2 个达到突发规则；但最后 5 分钟无买，支持较早资金累积，不支持临门聪明钱包点火。拉升段唯一标记买带 wash_trader，已被风险过滤。
├── 上升传播 ─ 官号在上升段继续运营，可能增强既有叙事。
└── 峰后内容 ─ 后续官号内容与下一波时间重叠，不能倒推二波。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @cetsongold · project_announcement · 创建后 3m08s。

证据计数：公开提前 `fresh=1` / `standing=5` / 最近提前 `2h39m`；+20% 前观测流 `27 买 / $2.3K / 6 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=0/$0`。

最佳支持机制：**项目运营 + 市场资金流**；置信度：**中低**。

反证：没有独立外部前瞻信号或合格钱包；1m OHLC high 在 17:08 UTC 先报 +20%，逐笔 provider 首跨越却到 17:16:14，数据源分歧使精确点火顺序不确定。

未知项：6 个普通买入钱包的历史与组织关系；是否有未采集 TG 触发。

可直连证据（完整回执见 JSONL 账本）：

- [x_project · closest-public-before-1.02/2h39m · 2026-08-10T14:04:17Z](https://x.com/i/status/2086815906576171218)
- [cetsongold · historical_baseline/banner_resource_timestamp · 2026-08-06T01:12:45Z](https://api.fxtwitter.com/cetsongold)
- [cetsongold · historical_baseline/project_announcement · 2026-08-06T02:59:34Z](https://x.com/cetsongold/status/2085199072928186463)
- [vutnerable · historical_baseline/market_thesis · 2026-08-06T03:03:23Z](https://x.com/vutnerable/status/2085200032832356537)
- [cetsongold · historical_baseline/project_announcement · 2026-08-06T03:14:56Z](https://x.com/cetsongold/status/2085202940441325620)
- [cetsongold · historical_baseline/post · 2026-08-06T03:38:30Z](https://x.com/cetsongold/status/2085208867819151399)
- [cetsongold · historical_baseline/post · 2026-08-06T04:07:37Z](https://x.com/cetsongold/status/2085216196190966204)
- [cetsongold · historical_baseline/post · 2026-08-06T04:27:06Z](https://x.com/cetsongold/status/2085221098388644291)

### 波 3 — 至少一条经复核公开信号早于 +2%

行情：`08-10 22:40 UTC` 低点 → `08-11 04:05 UTC` 峰值，`3.65x`，峰值 close-FDV $3.466M；首个交易级 +2% `08-10 22:48 UTC`；1m +20% 边界 `08-10 22:56 UTC candle（严格提前截止 08-10 22:56 UTC）`。

```text
最早叙事源 ─ 仍沿用既有 CETS/黄金叙事；没有发现新的独立上游来源。
├── 官号/头像 ─ 官号 22:00 的持有叙事早于 +2% 约 48m；后续 fire 帖在 +2% 后，只能算放大。
├── +2% 前信号 ─ 官号自推是可复核提前事件，但发生在 replay reset 前约 25m，故账本状态仍记 standing；真实提前量单列，不能误称预测型 KOL。
├── 链上点火 ─ 逐笔 provider 重放在 +20% 首跨越前有 9 笔买入、约 $157、9 个钱包，均无重复或突发特征；更像分散小额资金流，不能升级为聪明钱包点火。
├── 上升传播 ─ 官号及 Beast 频道在上升过程中接力，时间上不能称最早点火。
└── 峰后内容 ─ 持续官方运营延续至下一波。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @cetsongold · project_announcement · 创建后 3m08s。

证据计数：公开提前 `fresh=0` / `standing=8` / 最近提前 `48m14s`；+20% 前观测流 `9 买 / $157 / 9 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=0/$0`。

最佳支持机制：**项目运营 + 市场资金流**；置信度：**中低**。

反证：独立频道新动作晚于 +2%，且没有合格钱包证据；1m high 在 22:56 UTC 先报 +20%，但逐笔首跨越和首个 close-confirmed 均到约 23:32，必须保留 OHLC/逐笔源分歧。

未知项：9 个普通买入钱包是否相互独立；池子或聚合源差异为何产生约 36 分钟 high 偏移。

可直连证据（完整回执见 JSONL 账本）：

- [x_project · closest-public-before-1.02/48m14s · 2026-08-10T22:00:00Z](https://x.com/i/status/2086935622954954776)
- [cetsongold · historical_baseline/banner_resource_timestamp · 2026-08-06T01:12:45Z](https://api.fxtwitter.com/cetsongold)
- [cetsongold · historical_baseline/project_announcement · 2026-08-06T02:59:34Z](https://x.com/cetsongold/status/2085199072928186463)
- [vutnerable · historical_baseline/market_thesis · 2026-08-06T03:03:23Z](https://x.com/vutnerable/status/2085200032832356537)
- [cetsongold · historical_baseline/project_announcement · 2026-08-06T03:14:56Z](https://x.com/cetsongold/status/2085202940441325620)
- [cetsongold · historical_baseline/post · 2026-08-06T03:38:30Z](https://x.com/cetsongold/status/2085208867819151399)
- [cetsongold · historical_baseline/post · 2026-08-06T04:07:37Z](https://x.com/cetsongold/status/2085216196190966204)
- [cetsongold · historical_baseline/post · 2026-08-06T04:27:06Z](https://x.com/cetsongold/status/2085221098388644291)

### 波 4 — 至少一条经复核公开信号早于 +2%

行情：`08-11 08:10 UTC` 低点 → `08-11 15:00 UTC` 峰值，`2.21x`，峰值 close-FDV $4.067M；首个交易级 +2% `08-11 08:12 UTC`；1m +20% 边界 `08-11 08:23 UTC candle（严格提前截止 08-11 08:23 UTC）`。

```text
最早叙事源 ─ 既有项目叙事延续，本波前官号再次发布新内容。
├── 官号/头像 ─ 官号 07:54:49 状态早于交易级 +2% 17m24s，是可核验项目动作；头像资源仍不单列为原因。
├── +2% 前信号 ─ 官号新状态在启动前理论在线可见；因它早于 replay reset 约 2m，机器 freshness 仍为 standing，但真实提前秒数已单列。
├── 链上点火 ─ +20% 前观测 32 笔、约 $8,228；没有过滤后标记聪明钱拉升买入。
├── 上升传播 ─ CH1RO0 在 +2% 后、峰前喊话，属于上升放大；官号后续继续接力。
└── 峰后内容 ─ 频道与官号内容延续到第五波，需避免重复归因。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @cetsongold · project_announcement · 创建后 3m08s。

证据计数：公开提前 `fresh=0` / `standing=10` / 最近提前 `17m24s`；+20% 前观测流 `32 买 / $8.2K / 17 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=0/$0`。

最佳支持机制：**项目运营 + 市场资金流**；置信度：**中**。

反证：官号状态未必含独立外部认可；缺少点时合格钱包。

未知项：32 笔买入的资金聚类；启动前是否有 TG 先发。

可直连证据（完整回执见 JSONL 账本）：

- [x_project · closest-public-before-1.02/17m24s · 2026-08-11T07:54:49Z](https://x.com/i/status/2087085313009357049)
- [cetsongold · historical_baseline/banner_resource_timestamp · 2026-08-06T01:12:45Z](https://api.fxtwitter.com/cetsongold)
- [cetsongold · historical_baseline/project_announcement · 2026-08-06T02:59:34Z](https://x.com/cetsongold/status/2085199072928186463)
- [vutnerable · historical_baseline/market_thesis · 2026-08-06T03:03:23Z](https://x.com/vutnerable/status/2085200032832356537)
- [cetsongold · historical_baseline/project_announcement · 2026-08-06T03:14:56Z](https://x.com/cetsongold/status/2085202940441325620)
- [cetsongold · historical_baseline/post · 2026-08-06T03:38:30Z](https://x.com/cetsongold/status/2085208867819151399)
- [cetsongold · historical_baseline/post · 2026-08-06T04:07:37Z](https://x.com/cetsongold/status/2085216196190966204)
- [cetsongold · historical_baseline/post · 2026-08-06T04:27:06Z](https://x.com/cetsongold/status/2085221098388644291)

### 波 5 — 至少一条经复核公开信号早于 +2%

行情：`08-11 17:20 UTC` 低点 → `08-12 14:55 UTC` 峰值，`4.15x`，峰值 close-FDV $6.661M；首个交易级 +2% `08-11 17:25 UTC`；1m +20% 边界 `08-11 17:25 UTC candle（严格提前截止 08-11 17:25 UTC）`。

```text
最早叙事源 ─ 项目长期叙事已成熟；本波前 zygfridjournal 与其 X 状态重新提出 Exact-CA 观点。
├── 官号/头像 ─ 官号 14:42:53 的 $CETS 状态早于 +2% 约 2h42m；头像/banner 不作为因果证据。
├── +2% 前信号 ─ zygfridjournal TG/X 最近约早 1h47m，官号亦提前，CH1RO0 旧帖站岗；独立频道提供了本波最接近的公开前瞻线索。
├── 链上点火 ─ +20% 前观测 17 笔、约 $840；没有过滤后标记聪明钱拉升买入。
├── 上升传播 ─ zygfridjournal 在 +2% 后再次更新，PowsGemCalls 更晚接力；asianmarketcall 与 Pow 文案相同，只算复制传播。
└── 峰后内容 ─ DefiApeGems 等后续内容以复盘/延续为主，不重新记作独立点火。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @cetsongold · project_announcement · 创建后 3m08s。

证据计数：公开提前 `fresh=0` / `standing=14` / 最近提前 `1h47m`；+20% 前观测流 `17 买 / $841 / 4 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=0/$0`。

最佳支持机制：**新鲜公开论点 + 市场资金流**；置信度：**中**。

反证：早期 TG/X 与 +2% 相隔较长，可能只是站岗；多个频道存在复制文案，独立性有限。

未知项：最早频道间的转发路径；第五波主要资金来源。

可直连证据（完整回执见 JSONL 账本）：

- [x_exact · closest-public-before-1.02/1h47m · 2026-08-11T15:37:50Z](https://x.com/i/status/2087201834821976274)
- [cetsongold · historical_baseline/banner_resource_timestamp · 2026-08-06T01:12:45Z](https://api.fxtwitter.com/cetsongold)
- [cetsongold · historical_baseline/project_announcement · 2026-08-06T02:59:34Z](https://x.com/cetsongold/status/2085199072928186463)
- [vutnerable · historical_baseline/market_thesis · 2026-08-06T03:03:23Z](https://x.com/vutnerable/status/2085200032832356537)
- [cetsongold · historical_baseline/project_announcement · 2026-08-06T03:14:56Z](https://x.com/cetsongold/status/2085202940441325620)
- [cetsongold · historical_baseline/post · 2026-08-06T03:38:30Z](https://x.com/cetsongold/status/2085208867819151399)
- [cetsongold · historical_baseline/post · 2026-08-06T04:07:37Z](https://x.com/cetsongold/status/2085216196190966204)
- [cetsongold · historical_baseline/post · 2026-08-06T04:27:06Z](https://x.com/cetsongold/status/2085221098388644291)

## Asian games

### 波 1 — 仅同块待打包/Builder 理论可提前

行情：`08-08 12:20 UTC` 低点 → `08-09 01:15 UTC` 峰值，`1433.87x`，峰值 close-FDV $5.289M；首个交易级 +2% `08-08 12:23 UTC`；1m +20% 边界 `08-08 12:23 UTC candle（严格提前截止 08-08 12:23 UTC）`。

```text
最早叙事源 ─ 项目后续自述女娲社区/亚运会机制，但没有找到创建前可核验且含 Exact CA 的原始叙事。
├── 官号/头像 ─ 没有首波前官号或头像动作的直连证据；SellerOfOptions 更像项目/社区宣传方。
├── +2% 前信号 ─ +2% 与创建同秒同块；公开 Exact-CA 帖晚约 2 小时 34 分，普通确认流来不及，只有待打包/Builder 可理论提前。
├── 链上点火 ─ +20% 前仅 1 笔约 $9,825 的买入就跨越阈值，呈现高度集中的首笔资本点火；无过滤后标记买入。
├── 上升传播 ─ SellerOfOptions 在上升段补全金库、回购和社区机制，之后多个账号继续宣传。
└── 峰后内容 ─ 峰后仍有机制论证、Flap burn 扫描及推荐帖，均不能倒推启动原因。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @SellerOfOptions · market_thesis · 创建后 2h33m。

证据计数：公开提前 `fresh=0` / `standing=0` / 最近提前 `无公开提前信号`；+20% 前观测流 `1 买 / $9.8K / 1 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=0/$0`。

最佳支持机制：**同块资本先行**；置信度：**中**。

反证：首个公开项目帖远晚于点火；单笔大买可能是部署/做市或 bundle，不能称聪明钱。

未知项：首笔大买与创建者关系；女娲社区私域最早公告。

可直连证据（完整回执见 JSONL 账本）：

- [SellerOfOptions · ascent/market_thesis · 2026-08-08T14:57:32Z](https://x.com/SellerOfOptions/status/2086104528789876751)
- [sellerofoptions · decay/market_thesis · 2026-08-09T11:15:26Z](https://x.com/SellerOfOptions/status/2086411025004589083)
- [3895703285st · decay/market_thesis · 2026-08-09T17:27:34Z](https://x.com/3895703285st/status/2086504674837020854)
- [nmg_bld · decay/scanner · 2026-08-10T00:13:11Z](https://x.com/nmg_BLD/status/2086606750330012125)
- [tianyunzhanshen · decay/market_thesis · 2026-08-10T01:28:39Z](https://x.com/tianyunzhanshen/status/2086625744634233171)
- [BscScan · same_block_before · 0xe95a6e91…](https://bscscan.com/tx/0xe95a6e91f81a3fc0f46bcd0a7303362edfad149809814df8f0316cdb7c3cc7fc)

## bStocks

### 波 1 — 仅同块待打包/Builder 理论可提前

行情：`08-07 08:45 UTC` 低点 → `08-07 14:10 UTC` 峰值，`687.45x`，峰值 close-FDV $2.690M；首个交易级 +2% `08-07 08:46 UTC`；1m +20% 边界 `08-07 08:46 UTC candle（严格提前截止 08-07 08:46 UTC）`。

```text
最早叙事源 ─ Binance 08:03 发布贵金属期权内容，早于代币创建，但只是板块叙事种子；没有 Binance/CZ 对本 Exact CA 的认可。
├── 官号/头像 ─ @bstocksfinance 当前头像资源指示时间早于创建，但资源时间不是换头像动作证明；后续 banner 和官号短句也不能反推首波。
├── +2% 前信号 ─ 公开 Exact-CA 喊话全部晚于 +2%；首个跨阈值买入与 +2% 同块，普通确认流来不及，只能待打包/Builder 理论可见。
├── 链上点火 ─ +20% 前观测 3 笔、约 $517；首波拉升段过滤后买入 86 笔、约 $23,878，资金扩散证据强。
├── 上升传播 ─ feibo03、monkeyd_long 在 +2% 后 7–12 分钟将新 CA 绑定到 bStocks 账号，moneymancalls 后续强化 Binance/CZ 想象。
└── 峰后内容 ─ 52Hz_eth 复盘十倍，lhkayy11 在峰后警告非官方，后续还有板块盘点与二波喊话。
```

叙事源审计：上游叙事源有直连回执；首个有意义 Exact-CA 帖为 @feibo03 · market_thesis · 创建后 7m13s。

证据计数：公开提前 `fresh=0` / `standing=0` / 最近提前 `无公开提前信号`；+20% 前观测流 `3 买 / $517 / 3 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=86/$23.9K`。

最佳支持机制：**资本点火后社交放大**；置信度：**中**。

反证：Binance 原帖不含本 CA；早期 KOL 帖均晚于 +2%，不是提前触发。

未知项：同块首批交易是否由同一 bundle 组织；@bstocksfinance 与代币创建者的真实控制关系。

可直连证据（完整回执见 JSONL 账本）：

- [bstocksfinance · historical_baseline/avatar_resource_timestamp · 2026-08-07T06:52:15.830000Z](https://api.fxtwitter.com/bstocksfinance)
- [binance · token metadata narrative source · 2026-08-07T08:03:58Z](https://x.com/binance/status/2085638063414259744)
- [feibo03 · ascent/market_thesis · 2026-08-07T08:54:10Z](https://x.com/feibo03/status/2085650699095023692)
- [monkeyd_long · ascent/market_thesis · 2026-08-07T08:59:18Z](https://x.com/monkeyd_long/status/2085651990500249969)
- [lsxs_888 · ascent/relay · 2026-08-07T09:25:18Z](https://x.com/LSXS_888/status/2085658530548478426)
- [moneymancalls · ascent/market_thesis · 2026-08-07T11:53:16Z](https://x.com/moneymancalls/status/2085695771261739426)
- [sol_jingou · ascent/market_context · 2026-08-07T13:14:02Z](https://x.com/sol_jingou/status/2085716094506201511)
- [memeradar_sol · ascent/market_context · 2026-08-07T13:36:23Z](https://x.com/MemeRadar_sol/status/2085721718144839773)
- [BscScan · same_block_before · 0xb833b223…](https://bscscan.com/tx/0xb833b2233413f06ff94af508223412c9ba4f950d8568db60bafe9d999d8b9588)

### 波 2 — 至少一条经复核公开信号早于 +2%

行情：`08-10 17:45 UTC` 低点 → `08-12 12:00 UTC` 峰值，`6.23x`，峰值 close-FDV $3.916M；首个交易级 +2% `08-10 17:51 UTC`；1m +20% 边界 `08-10 20:52 UTC candle（严格提前截止 08-10 20:52 UTC）`。

```text
最早叙事源 ─ 首波形成的 bStocks/Binance 股票叙事已站岗；monkeyd_long 的板块盘点在本波前重新强化该定位。
├── 官号/头像 ─ @bstocksfinance 的“Not yet. But soon.”和“Almost time.”出现在本波上升途中，不是首个 +2% 前触发。
├── +2% 前信号 ─ 4 个公开事件在 +2% 前可见，但只有 monkeyd_long 为本波新鲜内容，其余是首波旧帖；这是叙事候选，不是已证明因果。
├── 链上点火 ─ +20% 前观测 222 笔、约 $20,019；拉升段仅 2 笔过滤后标记买入、约 $391，说明广泛交易流强于已标记聪明钱证据。
├── 上升传播 ─ 本波途中 the0xfrog、MEME_2ye 与 monkeyd_long 再次喊话，官号短句配合情绪扩散。
└── 峰后内容 ─ 峰值附近及之后主要是板块总结与追涨式讨论，没有独立的新官方认可。
```

叙事源审计：上游叙事源有直连回执；首个有意义 Exact-CA 帖为 @feibo03 · market_thesis · 创建后 7m13s。

证据计数：公开提前 `fresh=1` / `standing=3` / 最近提前 `48h33m`；+20% 前观测流 `222 买 / $20.0K / 126 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=2/$391`。

最佳支持机制：**旧叙事站岗 + 市场资金流**；置信度：**中**。

反证：多数所谓提前 KOL 是旧帖站岗；已标记钱包样本没有通过点时技能门禁。

未知项：大额交易流中真实独立钱包比例；官号短句与价格交易的协调关系。

可直连证据（完整回执见 JSONL 账本）：

- [x_exact · closest-public-before-1.02/48h33m · 2026-08-08T17:17:38Z](https://x.com/i/status/2086139789095641395)
- [bstocksfinance · historical_baseline/avatar_resource_timestamp · 2026-08-07T06:52:15.830000Z](https://api.fxtwitter.com/bstocksfinance)
- [binance · token metadata narrative source · 2026-08-07T08:03:58Z](https://x.com/binance/status/2085638063414259744)
- [feibo03 · historical_baseline/market_thesis · 2026-08-07T08:54:10Z](https://x.com/feibo03/status/2085650699095023692)
- [monkeyd_long · historical_baseline/market_thesis · 2026-08-07T08:59:18Z](https://x.com/monkeyd_long/status/2085651990500249969)
- [lsxs_888 · historical_baseline/relay · 2026-08-07T09:25:18Z](https://x.com/LSXS_888/status/2085658530548478426)
- [moneymancalls · historical_baseline/market_thesis · 2026-08-07T11:53:16Z](https://x.com/moneymancalls/status/2085695771261739426)
- [sol_jingou · historical_baseline/market_context · 2026-08-07T13:14:02Z](https://x.com/sol_jingou/status/2085716094506201511)

## BOT

### 波 1 — 仅同块待打包/Builder 理论可提前

行情：`08-09 19:50 UTC` 低点 → `08-09 20:05 UTC` 峰值，`359.32x`，峰值 close-FDV $1.595M；首个交易级 +2% `08-09 19:51 UTC`；1m +20% 边界 `08-09 19:51 UTC candle（严格提前截止 08-09 19:51 UTC）`。

```text
最早叙事源 ─ 创建后 false2z 首先公开指认“正确 CA”，SpeedevsO 再包装成 SpaceX affiliated @bot；SpaceX 关联没有官方证明。
├── 官号/头像 ─ BOT 头像/banner 约 20:55 才变化，已在首波重置后，明确不能解释首波。
├── +2% 前信号 ─ +2% 几乎与创建同时且处于同块，公开帖均来不及；只有待打包/Builder 理论可见首单。
├── 链上点火 ─ +20% 前观测 4 笔、约 $537；拉升段过滤后买入 27 笔、约 $11,250。
├── 上升传播 ─ false2z 在创建后约 1分52秒、+2% 后纠正 CA，SpeedevsO 随后给出 SpaceX 叙事，两者在首峰前完成放大。
└── 峰后内容 ─ 头像/横幅和项目账号动作在首波后出现，更多为二波准备或追认。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @false2z · market_thesis · 创建后 1m52s。

证据计数：公开提前 `fresh=0` / `standing=0` / 最近提前 `无公开提前信号`；+20% 前观测流 `4 买 / $537 / 4 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=27/$11.3K`。

最佳支持机制：**资本点火后社交放大**；置信度：**中高**。

反证：SpaceX 未认可本 CA 或项目；两个关键账号都晚于 +2%。

未知项：首个 bundle/创建者与传播者关系；所谓错误 CA 的竞争传播轨迹。

可直连证据（完整回执见 JSONL 账本）：

- [false2z · ascent/market_thesis · 2026-08-09T19:53:45Z](https://x.com/false2z/status/2086541464171860432)
- [SpeedevsO · ascent/market_thesis · 2026-08-09T20:03:33Z](https://x.com/SpeedevsO/status/2086543928061284777)
- [BscScan · same_block_before · 0x2a0593de…](https://bscscan.com/tx/0x2a0593de6e51e405bc80c8f2acae54b6caf4102ee841dd47be5c5430bb9d603c)

### 波 2 — 至少一条经复核公开信号早于 +2%

行情：`08-09 22:00 UTC` 低点 → `08-10 00:05 UTC` 峰值，`2.33x`，峰值 close-FDV $788.4K；首个交易级 +2% `08-09 22:06 UTC`；1m +20% 边界 `08-09 22:13 UTC candle（严格提前截止 08-09 22:13 UTC）`。

```text
最早叙事源 ─ false2z 的 CA 定盘和 SpeedevsO 的 SpaceX 包装已站岗，项目账号又在本波前发布 teaser。
├── 官号/头像 ─ 头像/banner 已在波间出现，但资源时间只能作动作线索；项目 teaser 的精确状态时间才可用。
├── +2% 前信号 ─ 两个独立旧帖和一个本波新鲜项目 teaser 均早于 +2%，在线订阅理论可捕捉。
├── 链上点火 ─ +20% 前观测 178 笔、约 $12,813；前 30 分钟有 1 笔过滤后买入约 $148，拉升段无过滤后标记买入。
├── 上升传播 ─ 旧 KOL 叙事、项目新动作与广泛交易流共同推动二次拉升，不能归于换头像单因。
└── 峰后内容 ─ 之后主要是项目延续和关联叙事，没有 SpaceX 官方补证。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @false2z · market_thesis · 创建后 1m52s。

证据计数：公开提前 `fresh=1` / `standing=2` / 最近提前 `1h04m`；+20% 前观测流 `178 买 / $12.8K / 121 钱包`；过滤后标记买入 `pre30=1/$148`，`ascent=0/$0`。

最佳支持机制：**新鲜公开论点 + 市场资金流**；置信度：**中**。

反证：头像时间不是 UI 操作的独立证明；独立喊话是首波旧帖而非二波新 KOL。

未知项：178 笔买入的关联钱包占比；项目 teaser 是否提前在私域发布。

可直连证据（完整回执见 JSONL 账本）：

- [x_project · closest-public-before-1.02/1h04m · 2026-08-09T21:01:48Z](https://x.com/i/status/2086558589452157121)
- [false2z · historical_baseline/market_thesis · 2026-08-09T19:53:45Z](https://x.com/false2z/status/2086541464171860432)
- [SpeedevsO · historical_baseline/market_thesis · 2026-08-09T20:03:33Z](https://x.com/SpeedevsO/status/2086543928061284777)
- [botonbnb · historical_baseline/avatar_resource_timestamp · 2026-08-09T20:55:11.706000Z](https://api.fxtwitter.com/BotOnBnb)
- [botonbnb · historical_baseline/post · 2026-08-09T21:01:48Z](https://x.com/botonbnb/status/2086558589452157121)

## fourclub

### 波 1 — 至少一条经复核公开信号早于 +2%

行情：`08-10 16:05 UTC` 低点 → `08-10 16:40 UTC` 峰值，`9.18x`，峰值 close-FDV $1.335M；首个交易级 +2% `08-10 16:10 UTC`；1m +20% 边界 `08-10 16:11 UTC candle（严格提前截止 08-10 16:11 UTC）`。

```text
最早叙事源 ─ 项目官号 16:02 直发 Exact CA 与 NFT/代币机制，是当前最早可核验的本项目来源。
├── 官号/头像 ─ 头像/banner 资源时间仅作旁证；真正可用的是 16:02 上线帖及 16:10 mint 开放状态。
├── +2% 前信号 ─ 项目上线帖早于 +2% 492 秒，mint 开放早 25 秒，均是本波新鲜、公开、Exact-CA 可绑定信号。
├── 链上点火 ─ +20% 前观测 36 笔、约 $5,599；拉升段过滤后买入 13 笔、约 $9,492。
├── 上升传播 ─ 官方产品发布与资金流同步，随后扫描器和社区帖扩散。
└── 峰后内容 ─ BscKOLScanner、钓鱼领取帖和 qkl2058 盈利复盘均晚于首波，后者不能当提前 KOL。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @4clubBNB · project_announcement · 创建后 13m40s。

证据计数：公开提前 `fresh=2` / `standing=0` / 最近提前 `25s`；+20% 前观测流 `36 买 / $5.6K / 24 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=13/$9.5K`。

最佳支持机制：**项目运营 + 市场资金流**；置信度：**中高**。

反证：时间吻合仍不证明官方帖单独造成买盘；所有标记钱包都未通过完整操纵/技能门禁。

未知项：mint 用户与代币买家重合度；首波有无私有预告。

可直连证据（完整回执见 JSONL 账本）：

- [x_project · closest-public-before-1.02/25s · 2026-08-10T16:10:31Z](https://x.com/i/status/2086847670971253158)
- [4clubbnb · historical_baseline/avatar_resource_timestamp · 2026-08-08T22:07:34.576000Z](https://api.fxtwitter.com/4clubBNB)
- [4clubBNB · pre_trough/project_announcement · 2026-08-10T16:02:44Z](https://x.com/4clubBNB/status/2086845714844295618)
- [4clubbnb · pre_trough/post · 2026-08-10T16:02:44Z](https://x.com/4clubbnb/status/2086845714844295618)
- [4clubbnb · ascent/post · 2026-08-10T16:10:31Z](https://x.com/4clubbnb/status/2086847670971253158)
- [4clubbnb · decay/post · 2026-08-10T16:45:17Z](https://x.com/4clubbnb/status/2086856423242092674)
- [4clubbnb · decay/reply · 2026-08-10T16:45:18Z](https://x.com/4clubbnb/status/2086856427205775533)
- [4clubbnb · decay/reply · 2026-08-10T16:45:19Z](https://x.com/4clubbnb/status/2086856429810471002)

### 波 2 — 至少一条经复核公开信号早于 +2%

行情：`08-10 18:00 UTC` 低点 → `08-10 18:45 UTC` 峰值，`2.49x`，峰值 close-FDV $1.589M；首个交易级 +2% `08-10 18:05 UTC`；1m +20% 边界 `08-10 18:05 UTC candle（严格提前截止 08-10 18:05 UTC）`。

```text
最早叙事源 ─ 首波项目叙事已建立，二波继续围绕 NFT、奖励和社区增长。
├── 官号/头像 ─ 官方在 +2% 前 205 秒发布最新状态，之前还有多条本波新鲜运营内容。
├── +2% 前信号 ─ 6 个官方事件可在 +2% 前看到，其中 4 个是本波新鲜；比单纯旧帖站岗更接近可执行催化。
├── 链上点火 ─ +20% 前观测 13 笔、约 $3,178；拉升段过滤后买入 5 笔、约 $5,918。
├── 上升传播 ─ 官方连续运营先行，BscKOLScanner 在上升段跟随，未发现更早的独立 KOL 点火。
└── 峰后内容 ─ 领取类钓鱼话术在回撤及更晚阶段大量复制，应从有效信号中排除。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @4clubBNB · project_announcement · 创建后 13m40s。

证据计数：公开提前 `fresh=4` / `standing=2` / 最近提前 `3m25s`；+20% 前观测流 `13 买 / $3.2K / 13 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=5/$5.9K`。

最佳支持机制：**项目运营 + 市场资金流**；置信度：**中高**。

反证：官方连续高频发帖使单帖贡献不可分辨；钱包标签尚无点时技能证明。

未知项：哪一条运营内容真正触发交易；二波买盘是否来自首波获利资金回流。

可直连证据（完整回执见 JSONL 账本）：

- [x_project · closest-public-before-1.02/3m25s · 2026-08-10T18:01:47Z](https://x.com/i/status/2086875673373639148)
- [4clubbnb · historical_baseline/avatar_resource_timestamp · 2026-08-08T22:07:34.576000Z](https://api.fxtwitter.com/4clubBNB)
- [4clubBNB · historical_baseline/project_announcement · 2026-08-10T16:02:44Z](https://x.com/4clubBNB/status/2086845714844295618)
- [4clubbnb · historical_baseline/post · 2026-08-10T16:02:44Z](https://x.com/4clubbnb/status/2086845714844295618)
- [4clubbnb · historical_baseline/post · 2026-08-10T16:10:31Z](https://x.com/4clubbnb/status/2086847670971253158)
- [4clubbnb · historical_baseline/post · 2026-08-10T16:45:17Z](https://x.com/4clubbnb/status/2086856423242092674)
- [4clubbnb · historical_baseline/reply · 2026-08-10T16:45:18Z](https://x.com/4clubbnb/status/2086856427205775533)
- [4clubbnb · historical_baseline/reply · 2026-08-10T16:45:19Z](https://x.com/4clubbnb/status/2086856429810471002)

### 波 3 — 至少一条经复核公开信号早于 +2%

行情：`08-11 05:05 UTC` 低点 → `08-11 09:45 UTC` 峰值，`4.27x`，峰值 close-FDV $715.4K；首个交易级 +2% `08-11 05:11 UTC`；1m +20% 边界 `08-11 05:12 UTC candle（严格提前截止 08-11 05:12 UTC）`。

```text
最早叙事源 ─ 既有项目叙事持续，第三波围绕 mint、卖出市场和奖励产品更新。
├── 官号/头像 ─ 最近一条官方产品/市场状态早于 +2% 854 秒，另有 6 条本波新鲜动作。
├── +2% 前信号 ─ 13 个官方事件在 +2% 前可见，7 个是本波新鲜；可捕捉但信号密度高、需要去重。
├── 链上点火 ─ +20% 前观测 4 笔、约 $1,187；没有过滤后标记聪明钱拉升买入。
├── 上升传播 ─ 上升中主要出现钓鱼领取、盈利复盘和 relay，均不是独立先行因子。
└── 峰后内容 ─ qkl2058 的精准狙击盈利帖及多条复制内容在峰后/后续出现。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @4clubBNB · project_announcement · 创建后 13m40s。

证据计数：公开提前 `fresh=7` / `standing=6` / 最近提前 `14m14s`；+20% 前观测流 `4 买 / $1.2K / 4 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=0/$0`。

最佳支持机制：**项目运营 + 市场资金流**；置信度：**中**。

反证：没有独立 KOL 或合格钱包确认；官方发帖与低笔数买盘之间因果不可直接证明。

未知项：产品更新的真实链上使用量；四笔早期买入的资金关联。

可直连证据（完整回执见 JSONL 账本）：

- [x_project · closest-public-before-1.02/14m14s · 2026-08-11T04:57:00Z](https://x.com/i/status/2087040563136565725)
- [4clubbnb · historical_baseline/avatar_resource_timestamp · 2026-08-08T22:07:34.576000Z](https://api.fxtwitter.com/4clubBNB)
- [4clubBNB · historical_baseline/project_announcement · 2026-08-10T16:02:44Z](https://x.com/4clubBNB/status/2086845714844295618)
- [4clubbnb · historical_baseline/post · 2026-08-10T16:02:44Z](https://x.com/4clubbnb/status/2086845714844295618)
- [4clubbnb · historical_baseline/post · 2026-08-10T16:10:31Z](https://x.com/4clubbnb/status/2086847670971253158)
- [4clubbnb · historical_baseline/post · 2026-08-10T16:45:17Z](https://x.com/4clubbnb/status/2086856423242092674)
- [4clubbnb · historical_baseline/reply · 2026-08-10T16:45:18Z](https://x.com/4clubbnb/status/2086856427205775533)
- [4clubbnb · historical_baseline/reply · 2026-08-10T16:45:19Z](https://x.com/4clubbnb/status/2086856429810471002)

### 波 4 — 至少一条经复核公开信号早于 +2%

行情：`08-11 18:35 UTC` 低点 → `08-11 19:30 UTC` 峰值，`2.74x`，峰值 close-FDV $503.6K；首个交易级 +2% `08-11 18:45 UTC`；1m +20% 边界 `08-11 18:46 UTC candle（严格提前截止 08-11 18:46 UTC）`。

```text
最早叙事源 ─ 第四波仍是同一项目产品/交易场景叙事，而非新 KOL 创造的新故事。
├── 官号/头像 ─ 本波前有 OKX/市场相关官方更新；最近的新鲜官方事件早于 +2% 13,440 秒。
├── +2% 前信号 ─ 15 个官方事件站岗，但仅 2 个属于本波新鲜；可发现项目活跃，不是精确到分钟的唯一触发。
├── 链上点火 ─ +20% 前观测 2 笔、约 $315；没有过滤后标记聪明钱拉升买入。
├── 上升传播 ─ 官方二级市场内容在上升段接力；外部扫描/钓鱼内容多为跟随。
└── 峰后内容 ─ 后续 sniper alert 与领取话术属于价格/流量反应，不计新爆点。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @4clubBNB · project_announcement · 创建后 13m40s。

证据计数：公开提前 `fresh=2` / `standing=13` / 最近提前 `3h44m`；+20% 前观测流 `2 买 / $315 / 2 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=0/$0`。

最佳支持机制：**项目运营 + 市场资金流**；置信度：**中**。

反证：最新官方动作距启动约 3.7 小时，时效较弱；极少早期买入不足以识别主导资金。

未知项：是否存在未采集的 TG 社区动员；波段启动前订单来源。

可直连证据（完整回执见 JSONL 账本）：

- [x_project · closest-public-before-1.02/3h44m · 2026-08-11T15:01:13Z](https://x.com/i/status/2087192618295845247)
- [4clubbnb · historical_baseline/avatar_resource_timestamp · 2026-08-08T22:07:34.576000Z](https://api.fxtwitter.com/4clubBNB)
- [4clubBNB · historical_baseline/project_announcement · 2026-08-10T16:02:44Z](https://x.com/4clubBNB/status/2086845714844295618)
- [4clubbnb · historical_baseline/post · 2026-08-10T16:02:44Z](https://x.com/4clubbnb/status/2086845714844295618)
- [4clubbnb · historical_baseline/post · 2026-08-10T16:10:31Z](https://x.com/4clubbnb/status/2086847670971253158)
- [4clubbnb · historical_baseline/post · 2026-08-10T16:45:17Z](https://x.com/4clubbnb/status/2086856423242092674)
- [4clubbnb · historical_baseline/reply · 2026-08-10T16:45:18Z](https://x.com/4clubbnb/status/2086856427205775533)
- [4clubbnb · historical_baseline/reply · 2026-08-10T16:45:19Z](https://x.com/4clubbnb/status/2086856429810471002)

## bNS

### 波 1 — 至少一条经复核公开信号早于 +2%

行情：`08-07 19:10 UTC` 低点 → `08-08 11:30 UTC` 峰值，`6.85x`，峰值 close-FDV $698.1K；首个交易级 +2% `08-07 19:16 UTC`；1m +20% 边界 `08-07 20:45 UTC candle（严格提前截止 08-07 20:45 UTC）`。

```text
最早叙事源 ─ Binance 贵金属期权帖是 bStocks 板块种子；ojkared 首次把 bNS Exact CA 和“bStocks Never Sleep”明确绑定。
├── 官号/头像 ─ @bstocksfinance 头像资源线索早于代币，但不是动作证明，也没有对 bNS Exact CA 的官方认可。
├── +2% 前信号 ─ ojkared 的 Exact-CA 论点早于 +2% 约 9小时58分，属于本波新鲜公开信号，但时距较长。
├── 链上点火 ─ +20% 前观测 62 笔、约 $3,331；拉升段过滤后买入 17 笔、约 $5,732。
├── 上升传播 ─ 板块账户与 bStocks 叙事提供联想，后续市场盘点继续将 bNS 归为小弟。
└── 峰后内容 ─ bstocksfinance 的“soon”发生在更后阶段，不能解释首波。
```

叙事源审计：上游叙事源有直连回执；首个有意义 Exact-CA 帖为 @ojkared8139 · market_thesis · 创建后 27m13s。

证据计数：公开提前 `fresh=1` / `standing=0` / 最近提前 `9h57m`；+20% 前观测流 `62 买 / $3.3K / 38 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=17/$5.7K`。

最佳支持机制：**新鲜公开论点 + 市场资金流**；置信度：**中**。

反证：Binance 未认可 bNS CA；提前帖距启动近 10 小时且账号技能未获证明。

未知项：ojkared 帖的真实触达量；bNS 创建者与 bStocks 账号关系。

可直连证据（完整回执见 JSONL 账本）：

- [x_exact · closest-public-before-1.02/9h57m · 2026-08-07T09:19:01Z](https://x.com/i/status/2085656949635645872)
- [bstocksfinance · historical_baseline/avatar_resource_timestamp · 2026-08-07T06:52:15.830000Z](https://api.fxtwitter.com/bstocksfinance)
- [binance · token metadata narrative source · 2026-08-07T08:03:58Z](https://x.com/binance/status/2085638063414259744)
- [oxtrustbro · historical_baseline/negative_warning · 2026-08-07T09:07:40Z](https://x.com/oxtrustbro/status/2085654094773952538)
- [ojkared8139 · historical_baseline/market_thesis · 2026-08-07T09:19:01Z](https://x.com/ojkared8139/status/2085656949635645872)
- [sol_jingou · historical_baseline/market_context · 2026-08-07T13:14:02Z](https://x.com/sol_jingou/status/2085716094506201511)
- [googoocalls · decay/recap · 2026-08-08T11:46:07Z](https://x.com/googoocalls/status/2086056356487008742)

### 波 2 — 至少一条经复核公开信号早于 +2%

行情：`08-08 17:30 UTC` 低点 → `08-09 01:05 UTC` 峰值，`2.09x`，峰值 close-FDV $681.7K；首个交易级 +2% `08-08 17:38 UTC`；1m +20% 边界 `08-08 18:52 UTC candle（严格提前截止 08-08 18:52 UTC）`。

```text
最早叙事源 ─ ojkared/bStocks Never Sleep 论点已站岗，二波前没有新原创来源。
├── 官号/头像 ─ @bstocksfinance 头像仅为资源指示，没有本波前新动作。
├── +2% 前信号 ─ 一个公开 Exact-CA 帖早于 +2%，但属于约 32 小时前旧帖，不是本波新爆点。
├── 链上点火 ─ +20% 前观测 83 笔、约 $6,535；拉升段过滤后仅 1 笔约 $119。
├── 上升传播 ─ 既有板块叙事与交易流维持二波，没有发现先行新 KOL。
└── 峰后内容 ─ 后续账号 banner 和短句均更晚。
```

叙事源审计：上游叙事源有直连回执；首个有意义 Exact-CA 帖为 @ojkared8139 · market_thesis · 创建后 27m13s。

证据计数：公开提前 `fresh=0` / `standing=1` / 最近提前 `32h19m`；+20% 前观测流 `83 买 / $6.5K / 61 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=1/$119`。

最佳支持机制：**旧叙事站岗 + 市场资金流**；置信度：**中低**。

反证：仅有旧帖站岗；过滤后标记资金很弱。

未知项：普通交易流中资金聚类；二波私域传播。

可直连证据（完整回执见 JSONL 账本）：

- [x_exact · closest-public-before-1.02/32h19m · 2026-08-07T09:19:01Z](https://x.com/i/status/2085656949635645872)
- [bstocksfinance · historical_baseline/avatar_resource_timestamp · 2026-08-07T06:52:15.830000Z](https://api.fxtwitter.com/bstocksfinance)
- [binance · token metadata narrative source · 2026-08-07T08:03:58Z](https://x.com/binance/status/2085638063414259744)
- [oxtrustbro · historical_baseline/negative_warning · 2026-08-07T09:07:40Z](https://x.com/oxtrustbro/status/2085654094773952538)
- [ojkared8139 · historical_baseline/market_thesis · 2026-08-07T09:19:01Z](https://x.com/ojkared8139/status/2085656949635645872)
- [sol_jingou · historical_baseline/market_context · 2026-08-07T13:14:02Z](https://x.com/sol_jingou/status/2085716094506201511)
- [googoocalls · historical_baseline/recap · 2026-08-08T11:46:07Z](https://x.com/googoocalls/status/2086056356487008742)
- [monkeyd_long · pre_trough/market_context · 2026-08-08T17:17:38Z](https://x.com/monkeyd_long/status/2086139789095641395)

### 波 3 — 至少一条经复核公开信号早于 +2%

行情：`08-10 15:35 UTC` 低点 → `08-12 09:55 UTC` 峰值，`6.00x`，峰值 close-FDV $776.0K；首个交易级 +2% `08-10 15:40 UTC`；1m +20% 边界 `08-10 15:44 UTC candle（严格提前截止 08-10 15:44 UTC）`。

```text
最早叙事源 ─ bStocks Never Sleep 叙事继续站岗，未发现第三波前新的 Exact-CA 原创论点。
├── 官号/头像 ─ @bstocksfinance 的 banner 已存在；“Not yet. But soon.”和“Almost time.”在本波上升途中，且并不直认 bNS CA。
├── +2% 前信号 ─ 仅 ojkared 旧帖早于 +2%，没有本波新鲜公开信号。
├── 链上点火 ─ +20% 前观测 26 笔、约 $3,565；拉升段过滤后 2 笔、约 $932。
├── 上升传播 ─ bstocksfinance 短句在上升段可能放大整个板块想象，但与 bNS 的绑定是市场二次解释。
└── 峰后内容 ─ 后续板块盘点强化从属关系，不构成第三波点火。
```

叙事源审计：上游叙事源有直连回执；首个有意义 Exact-CA 帖为 @ojkared8139 · market_thesis · 创建后 27m13s。

证据计数：公开提前 `fresh=0` / `standing=1` / 最近提前 `78h21m`；+20% 前观测流 `26 买 / $3.6K / 21 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=2/$932`。

最佳支持机制：**旧叙事站岗 + 市场资金流**；置信度：**中低**。

反证：官号短句不含 bNS Exact CA；没有新 KOL 或技能合格钱包。

未知项：短句是否针对任何特定代币；第三波买家来源。

可直连证据（完整回执见 JSONL 账本）：

- [x_exact · closest-public-before-1.02/78h21m · 2026-08-07T09:19:01Z](https://x.com/i/status/2085656949635645872)
- [bstocksfinance · historical_baseline/avatar_resource_timestamp · 2026-08-07T06:52:15.830000Z](https://api.fxtwitter.com/bstocksfinance)
- [binance · token metadata narrative source · 2026-08-07T08:03:58Z](https://x.com/binance/status/2085638063414259744)
- [oxtrustbro · historical_baseline/negative_warning · 2026-08-07T09:07:40Z](https://x.com/oxtrustbro/status/2085654094773952538)
- [ojkared8139 · historical_baseline/market_thesis · 2026-08-07T09:19:01Z](https://x.com/ojkared8139/status/2085656949635645872)
- [sol_jingou · historical_baseline/market_context · 2026-08-07T13:14:02Z](https://x.com/sol_jingou/status/2085716094506201511)
- [googoocalls · historical_baseline/recap · 2026-08-08T11:46:07Z](https://x.com/googoocalls/status/2086056356487008742)
- [monkeyd_long · historical_baseline/market_context · 2026-08-08T17:17:38Z](https://x.com/monkeyd_long/status/2086139789095641395)

## 月薪喵

### 波 1 — 仅前一区块资金可普通确认

行情：`08-06 10:00 UTC` 低点 → `08-06 10:40 UTC` 峰值，`27.86x`，峰值 close-FDV $723.6K；首个交易级 +2% `08-06 10:05 UTC`；1m +20% 边界 `08-06 10:07 UTC candle（严格提前截止 08-06 10:07 UTC）`。

```text
最早叙事源 ─ xxlb888 在 05-24 解释抖音爆火的月薪喵，是已核验 meme 源；元数据链接不等于其认可本代币。
├── 官号/头像 ─ @yuexinmiao 账号、banner、头像均在三波结束后才出现，已证伪头像/官号点火。
├── +2% 前信号 ─ 无合格公开 Exact-CA 提前喊话；前一区块买入可由普通确认流理论看到，扫描器不算新叙事/KOL。
├── 链上点火 ─ 前 30 分钟过滤后 12 笔约 $1,326；+20% 前观测 52 笔约 $3,277；拉升段再有 14 笔约 $8,167。
├── 上升传播 ─ 首波中出现自动扫描，属于异动发现而非原创叙事。
└── 峰后内容 ─ 后续复盘和官号建立均不能倒推首波。
```

叙事源审计：上游叙事源有直连回执；首个有意义 Exact-CA 帖为 @baleabtc · market_thesis · 创建后 109h09m。

证据计数：公开提前 `fresh=0` / `standing=0` / 最近提前 `无公开提前信号`；+20% 前观测流 `52 买 / $3.3K / 43 钱包`；过滤后标记买入 `pre30=12/$1.3K`，`ascent=14/$8.2K`。

最佳支持机制：**前一区块资本先行**；置信度：**中**。

反证：原 meme 帖与代币相隔数月且不含本 CA；标记钱包未通过技能门禁。

未知项：代币部署者如何选择 meme；首批钱包是否协调。

可直连证据（完整回执见 JSONL 账本）：

- [xxlb888 · token metadata earliest meme source · 2026-05-24T09:20:12Z](https://x.com/xxlb888/status/2058478160115851723)
- [bsckolscanner · historical_baseline/scanner · 2026-08-06T09:21:14Z](https://x.com/BscKOLScanner/status/2085295120534962294)
- [BscScan · previous_block · 0x8f185be6…](https://bscscan.com/tx/0x8f185be6e83f4fd0b4e37bb122205b040bdf65d82be137d6cedac5f07115574e)
- [BscScan · previous_block · 0xc8ff9ef4…](https://bscscan.com/tx/0xc8ff9ef45b00a6fb602b39c73b350519fddfd22a0b92e1855f4f350910778c25)

### 波 2 — 仅前一区块资金可普通确认

行情：`08-06 15:55 UTC` 低点 → `08-06 21:45 UTC` 峰值，`5.30x`，峰值 close-FDV $954.2K；首个交易级 +2% `08-06 16:00 UTC`；1m +20% 边界 `08-06 16:00 UTC candle（严格提前截止 08-06 16:00 UTC）`。

```text
最早叙事源 ─ 抖音猫 meme 与首波市场注意力已站岗，但没有二波前新的公开叙事。
├── 官号/头像 ─ 官号和头像仍尚未出现。
├── +2% 前信号 ─ 无公开提前信号；前一区块交易可确认，属于链上而非 KOL 通道。
├── 链上点火 ─ +20% 前观测 6 笔、约 $2,819；拉升段过滤后买入 16 笔、约 $9,468。
├── 上升传播 ─ 未发现二波前独立喊话，价格与资金流本身成为后续传播源。
└── 峰后内容 ─ 后续账号建立发生在第三波也结束之后。
```

叙事源审计：上游叙事源有直连回执；首个有意义 Exact-CA 帖为 @baleabtc · market_thesis · 创建后 109h09m。

证据计数：公开提前 `fresh=0` / `standing=0` / 最近提前 `无公开提前信号`；+20% 前观测流 `6 买 / $2.8K / 5 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=16/$9.5K`。

最佳支持机制：**前一区块资本先行**；置信度：**中**。

反证：没有二波特定公开催化；钱包标签没有控制组技能证明。

未知项：6 笔大额买入是否同源；首波持仓者在二波的买卖结构。

可直连证据（完整回执见 JSONL 账本）：

- [xxlb888 · token metadata earliest meme source · 2026-05-24T09:20:12Z](https://x.com/xxlb888/status/2058478160115851723)
- [bsckolscanner · historical_baseline/scanner · 2026-08-06T09:21:14Z](https://x.com/BscKOLScanner/status/2085295120534962294)
- [bsckolscanner · historical_baseline/scanner · 2026-08-06T11:08:50Z](https://x.com/BscKOLScanner/status/2085322201448816954)
- [BscScan · previous_block · 0x58adfde4…](https://bscscan.com/tx/0x58adfde4c39f91baf6d9d4c85ebd808082e3592912671982a5c444c4e6e5374c)
- [BscScan · previous_block · 0xd97cc21d…](https://bscscan.com/tx/0xd97cc21da5bce999b80524deeadfeeb18d8fee8456b81e4858c73e68a9082833)

### 波 3 — 仅前一区块资金可普通确认

行情：`08-07 03:55 UTC` 低点 → `08-07 07:15 UTC` 峰值，`2.94x`，峰值 close-FDV $1.146M；首个交易级 +2% `08-07 04:00 UTC`；1m +20% 边界 `08-07 04:50 UTC candle（严格提前截止 08-07 04:50 UTC）`。

```text
最早叙事源 ─ 既有 meme 与前两波表现提供站岗注意力；没有第三波新原创叙事。
├── 官号/头像 ─ 官号/头像在本波结束后约数小时才出现。
├── +2% 前信号 ─ 无合格公开提前信号；前一区块资金可理论捕捉，早前复盘不算独立预测信号。
├── 链上点火 ─ +20% 前观测 185 笔、约 $13,800；拉升段过滤后仅 2 笔约 $575，广泛普通流占主导。
├── 上升传播 ─ 此前复盘可能维持注意力，但语义为 recap，不能当第三波新 KOL。
└── 峰后内容 ─ 官方账号随后建立并持续发布猫图，只能解释后续品牌化，不能解释三波。
```

叙事源审计：上游叙事源有直连回执；首个有意义 Exact-CA 帖为 @baleabtc · market_thesis · 创建后 109h09m。

证据计数：公开提前 `fresh=0` / `standing=0` / 最近提前 `无公开提前信号`；+20% 前观测流 `185 买 / $13.8K / 110 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=2/$575`。

最佳支持机制：**前一区块资本先行**；置信度：**中**。

反证：大部分交易无法归为已核验聪明钱包；旧复盘与第三波间因果不清。

未知项：185 笔交易的独立性；官号创建者与代币方关系。

可直连证据（完整回执见 JSONL 账本）：

- [xxlb888 · token metadata earliest meme source · 2026-05-24T09:20:12Z](https://x.com/xxlb888/status/2058478160115851723)
- [bsckolscanner · historical_baseline/scanner · 2026-08-06T09:21:14Z](https://x.com/BscKOLScanner/status/2085295120534962294)
- [bsckolscanner · historical_baseline/scanner · 2026-08-06T11:08:50Z](https://x.com/BscKOLScanner/status/2085322201448816954)
- [lsxs_888 · historical_baseline/recap · 2026-08-07T03:00:04Z](https://x.com/LSXS_888/status/2085561586077634914)
- [lsxs_888 · historical_baseline/relay · 2026-08-07T03:00:05Z](https://x.com/LSXS_888/status/2085561590175486355)
- [BscScan · previous_block · 0x0b5d681a…](https://bscscan.com/tx/0x0b5d681a2c6fd9736cb58e38a5e2a1d6fbe1e0277e5dd283501135c3a1a3339a)
- [BscScan · previous_block · 0x8fa7fd9b…](https://bscscan.com/tx/0x8fa7fd9bcf9f8df83d764b0b82d20a76e0fdaf5530490020e1995211da157f07)

## TKM

### 波 1 — 仅同块待打包/Builder 理论可提前

行情：`08-06 10:30 UTC` 低点 → `08-06 11:10 UTC` 峰值，`225.96x`，峰值 close-FDV $1.107M；首个交易级 +2% `08-06 10:30 UTC`；1m +20% 边界 `08-06 10:30 UTC candle（严格提前截止 08-06 10:30 UTC）`。

```text
最早叙事源 ─ TKM_AI/Flap 元数据存在，但未找到创建前的可核验公开 Exact-CA 叙事源。
├── 官号/头像 ─ 没有首波前头像/官号动作；项目 burn 帖在峰后。
├── +2% 前信号 ─ 创建后首个大买与 +2% 同块，仅待打包/Builder 理论可见；公开扫描器和项目帖都来不及。
├── 链上点火 ─ +20% 前 1 笔约 $9,705 的买入跨阈值；拉升段仅 1 笔过滤后标记买入约 $117。
├── 上升传播 ─ NMG_BLD 扫描器约 12:57、项目 burn 约 13:01 才出现，均晚于 11:10 峰值。
└── 峰后内容 ─ 已核验公开内容全部属于峰后检测/项目补叙事。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @tkm__ai · project_announcement · 创建后 2h31m。

证据计数：公开提前 `fresh=0` / `standing=0` / 最近提前 `无公开提前信号`；+20% 前观测流 `1 买 / $9.7K / 1 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=1/$117`。

最佳支持机制：**同块资本先行**；置信度：**中**。

反证：单笔大买未证明独立或有技能；没有公开提前传播证据。

未知项：大买与创建/做市方关系；TKM_AI 私域是否有更早公告。

可直连证据（完整回执见 JSONL 账本）：

- [BscScan · same_block_before · 0xd940c4de…](https://bscscan.com/tx/0xd940c4de2add5c362917d61882b604bbdb5edccd85cedc0b408635a32f14494f)

## Racoonzilla

### 波 1 — 仅前一区块资金可普通确认

行情：`08-08 03:10 UTC` 低点 → `08-08 05:00 UTC` 峰值，`219.53x`，峰值 close-FDV $963.3K；首个交易级 +2% `08-08 03:11 UTC`；1m +20% 边界 `08-08 03:11 UTC candle（严格提前截止 08-08 03:11 UTC）`。

```text
最早叙事源 ─ 上游浣熊/马斯克叙事原帖未找回；PlanetOfMemes 候选帖已删除，不能当作已核验源。
├── 官号/头像 ─ 项目头像资源时间为 04:16，官号 04:21 才开始发帖，均晚于 03:11 的 +2%，不能解释点火。
├── +2% 前信号 ─ 公开面无 +2% 前 Exact-CA 信号；前一区块有可确认买入，普通节点理论可在下一块前看到。
├── 链上点火 ─ 前一区块至少 1 笔已核验买入；+20% 前观测 9 笔、约 $449；拉升段过滤后买入 42 笔、约 $10,508。
├── 上升传播 ─ eth200000 在 +2% 后约 14 分钟发持仓判断，Crypto_Cat888 后续回复，项目官号再接力；属于放大而非点火。
└── 峰后内容 ─ brixtonmun7614 在峰后发布 Dexape 涨幅复盘，monkeyd_long 更晚纳入板块盘点。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @eth200000 · own_position · 创建后 14m45s。

证据计数：公开提前 `fresh=0` / `standing=0` / 最近提前 `无公开提前信号`；+20% 前观测流 `9 买 / $449 / 9 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=42/$10.5K`。

最佳支持机制：**资本点火后社交放大**；置信度：**中**。

反证：头像和官号动作均晚于启动；前一区块买家未通过历史技能门禁。

未知项：最初资金组织者及私有群传播；已删除上游叙事的准确时间和内容。

可直连证据（完整回执见 JSONL 账本）：

- [None · token metadata narrative source; currently deleted · ](https://x.com/PlanetOfMemes/status/2085926759644496195)
- [eth200000 · ascent/own_position · 2026-08-08T03:26:08Z](https://x.com/eth200000/status/2085930533658452365)
- [crypto_cat888 · ascent/reply_mention · 2026-08-08T04:09:49Z](https://x.com/Crypto_Cat888/status/2085941524836286478)
- [racoonzillabnb · ascent/avatar_resource_timestamp · 2026-08-08T04:16:16.453000Z](https://api.fxtwitter.com/RacoonzillaBNB)
- [racoonzillabnb · ascent/post · 2026-08-08T04:21:04Z](https://x.com/racoonzillabnb/status/2085944356305850638)
- [racoonzillabnb · ascent/post · 2026-08-08T04:24:57Z](https://x.com/racoonzillabnb/status/2085945336133038136)
- [racoonzillabnb · ascent/post · 2026-08-08T05:01:16Z](https://x.com/racoonzillabnb/status/2085954475840127312)
- [brixtonmun7614 · decay/recap · 2026-08-08T05:41:38Z](https://x.com/brixtonmun7614/status/2085964633010233404)
- [BscScan · previous_block · 0xf37747db…](https://bscscan.com/tx/0xf37747dbf1461b89deb33cf2aa710a2c5e35daef341288c93aa3a690b98dd175)

## XchangetheWorld

### 波 1 — 至少一条经复核公开信号早于 +2%

行情：`08-09 07:20 UTC` 低点 → `08-09 13:20 UTC` 峰值，`3.70x`，峰值 close-FDV $974.5K；首个交易级 +2% `08-09 07:25 UTC`；1m +20% 边界 `08-09 07:42 UTC candle（严格提前截止 08-09 07:42 UTC）`。

```text
最早叙事源 ─ CZ 06-01 的“Exchange the world!”是已核验上游口号源，但不认可本代币；Will_binance 和项目账号完成 Exact-CA/项目绑定。
├── 官号/头像 ─ 项目头像/banner 资源在波前出现，只作线索；可依赖的是 TG 上线、BinanceWallet/Flap 进展等精确状态。
├── +2% 前信号 ─ 5 个公开事件在 +2% 前可见，均为本波新鲜项目/独立传播，最晚约 5.2 小时前。
├── 链上点火 ─ +20% 前观测 70 笔、约 $4,986；拉升段仅 1 笔过滤后标记买入约 $115。
├── 上升传播 ─ 项目官号在上升、回撤中持续运营，将 CZ/Binance 口号叙事不断具体化。
└── 峰后内容 ─ 持仓、社区规模及口号帖继续发出，需区分运营延续与新催化。
```

叙事源审计：上游叙事源有直连回执；首个有意义 Exact-CA 帖为 @Will_binance · market_thesis · 创建后 23h02m。

证据计数：公开提前 `fresh=5` / `standing=0` / 最近提前 `5h13m`；+20% 前观测流 `70 买 / $5.0K / 47 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=1/$115`。

最佳支持机制：**项目运营 + 市场资金流**；置信度：**中**。

反证：CZ 原帖与本 CA 无关；提前项目帖距启动数小时，无法证明直接触发。

未知项：Will_binance 与项目方关系；70 笔早期买入的资金关联。

可直连证据（完整回执见 JSONL 账本）：

- [x_project · closest-public-before-1.02/5h13m · 2026-08-09T02:11:44Z](https://x.com/i/status/2086274197068656818)
- [cz_binance · token metadata slogan source · 2026-06-01T14:09:58Z](https://x.com/cz_binance/status/2061450186107301913)
- [Will_binance · historical_baseline/market_thesis · 2026-08-08T14:10:42Z](https://x.com/Will_binance/status/2086092743408071070)
- [oxxiaoqi · historical_baseline/negative_warning · 2026-08-08T14:32:41Z](https://x.com/Oxxiaoqi/status/2086098277372764555)
- [xchange_bsc · historical_baseline/avatar_resource_timestamp · 2026-08-08T14:45:49.425000Z](https://api.fxtwitter.com/Xchange_bsc)
- [xchange_bsc · historical_baseline/post · 2026-08-08T16:11:24Z](https://x.com/xchange_bsc/status/2086123119320998231)
- [xchange_bsc · historical_baseline/post · 2026-08-08T16:55:59Z](https://x.com/xchange_bsc/status/2086134337301533183)
- [xchange_bsc · historical_baseline/post · 2026-08-09T01:36:13Z](https://x.com/xchange_bsc/status/2086265257648099391)

### 波 2 — 至少一条经复核公开信号早于 +2%

行情：`08-10 22:10 UTC` 低点 → `08-12 10:15 UTC` 峰值，`5.28x`，峰值 close-FDV $660.1K；首个交易级 +2% `08-10 22:14 UTC`；1m +20% 边界 `08-10 22:23 UTC candle（严格提前截止 08-10 22:23 UTC）`。

```text
最早叙事源 ─ 既有 CZ/Binance 口号叙事已成熟，项目在本波前用银行+Binance emoji 再次提示。
├── 官号/头像 ─ 精确状态 🏦🔶 早于 +2% 877 秒，是本波最近的新鲜项目动作；头像不参与因果判断。
├── +2% 前信号 ─ 7 个公开事件早于 +2%，其中 2 个是本波新鲜，项目动作具备在线捕捉条件。
├── 链上点火 ─ +20% 前观测 31 笔、约 $2,354；没有过滤后标记聪明钱拉升买入。
├── 上升传播 ─ 项目上升中连续对比 Marscoin、CZ 与 Binance，并发布回归 BinanceWallet 股票区等内容。
└── 峰后内容 ─ 峰后继续做 Binance/X 叙事类比，属于运营延续。
```

叙事源审计：上游叙事源有直连回执；首个有意义 Exact-CA 帖为 @Will_binance · market_thesis · 创建后 23h02m。

证据计数：公开提前 `fresh=2` / `standing=5` / 最近提前 `14m37s`；+20% 前观测流 `31 买 / $2.4K / 27 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=0/$0`。

最佳支持机制：**项目运营 + 市场资金流**；置信度：**中高**。

反证：emoji 含义存在解释空间；没有独立 KOL 与合格钱包交叉确认。

未知项：项目帖曝光与成交的分钟级转化；普通买家的来源渠道。

可直连证据（完整回执见 JSONL 账本）：

- [x_project · closest-public-before-1.02/14m37s · 2026-08-10T22:00:07Z](https://x.com/i/status/2086935651761414419)
- [cz_binance · token metadata slogan source · 2026-06-01T14:09:58Z](https://x.com/cz_binance/status/2061450186107301913)
- [Will_binance · historical_baseline/market_thesis · 2026-08-08T14:10:42Z](https://x.com/Will_binance/status/2086092743408071070)
- [oxxiaoqi · historical_baseline/negative_warning · 2026-08-08T14:32:41Z](https://x.com/Oxxiaoqi/status/2086098277372764555)
- [xchange_bsc · historical_baseline/avatar_resource_timestamp · 2026-08-08T14:45:49.425000Z](https://api.fxtwitter.com/Xchange_bsc)
- [xchange_bsc · historical_baseline/post · 2026-08-08T16:11:24Z](https://x.com/xchange_bsc/status/2086123119320998231)
- [xchange_bsc · historical_baseline/post · 2026-08-08T16:55:59Z](https://x.com/xchange_bsc/status/2086134337301533183)
- [xchange_bsc · historical_baseline/post · 2026-08-09T01:36:13Z](https://x.com/xchange_bsc/status/2086265257648099391)

## CSI

### 波 1 — 仅同块待打包/Builder 理论可提前

行情：`08-09 21:40 UTC` 低点 → `08-09 22:00 UTC` 峰值，`240.18x`，峰值 close-FDV $847.1K；首个交易级 +2% `08-09 21:44 UTC`；1m +20% 边界 `08-09 21:44 UTC candle（严格提前截止 08-09 21:44 UTC）`。

```text
最早叙事源 ─ 未找到首波前可直连的原始叙事源；CSI 官号和 Exact-CA 内容均在启动后出现。
├── 官号/头像 ─ 官号/头像约 22:28 才出现，晚于首波 22:00 峰值，已证伪头像或官号点火。
├── +2% 前信号 ─ 无公开提前信号；首个 +2% 交易所在同块，普通区块确认无法提前。
├── 链上点火 ─ +20% 前观测 7 笔、约 $391；拉升段过滤后标记买入 9 笔、约 $4,095。
├── 上升传播 ─ KlausAlphaHQ 扫描器在首波结束后、二波上升中出现，只能视为价格反应型发现。
└── 峰后内容 ─ 后续 CSI 官号活动和 phishing_lure 都发生在前两波之后。
```

叙事源审计：只找到 scanner 等非叙事观察；未找到有意义 Exact-CA 公开帖。

证据计数：公开提前 `fresh=0` / `standing=0` / 最近提前 `无公开提前信号`；+20% 前观测流 `7 买 / $392 / 7 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=9/$4.1K`。

最佳支持机制：**同块资本先行**；置信度：**中低**。

反证：没有首波前公开 Exact-CA 或官号动作；链上标签不等于经过验证的聪明钱包。

未知项：同块首批订单来源；代币叙事在私域中的最早传播。

可直连证据（完整回执见 JSONL 账本）：

- [BscScan · same_block_before · 0xd7650995…](https://bscscan.com/tx/0xd76509957dfec83de069dff310af8c8efdfca30206deec2c7aa5c256a44eaf32)
- [BscScan · same_block_before · 0x64dcd253…](https://bscscan.com/tx/0x64dcd2532be593f8ad04b355b92dd3f9934272a20364cc5f8de4512e13cb8dba)

### 波 2 — 仅前一区块资金可普通确认

行情：`08-09 22:05 UTC` 低点 → `08-09 22:15 UTC` 峰值，`2.65x`，峰值 close-FDV $611.0K；首个交易级 +2% `08-09 22:09 UTC`；1m +20% 边界 `08-09 22:09 UTC candle（严格提前截止 08-09 22:09 UTC）`。

```text
最早叙事源 ─ 首波刚结束形成即时市场注意力，但仍无已核验的独立原始叙事。
├── 官号/头像 ─ 官号/头像仍晚于二波峰值，不能解释二波启动。
├── +2% 前信号 ─ 无合格公开提前信号；前一区块已有可确认买入，普通节点理论可见。
├── 链上点火 ─ 前 30 分钟含首波延续的 9 笔过滤后买入、约 $4,095；+20% 前观测 9 笔、约 $3,684；本波拉升段再有 4 笔、约 $1,695。
├── 上升传播 ─ KlausAlphaHQ 扫描器在上升段出现，但语义为 scanner，属于异动检测而非新叙事。
└── 峰后内容 ─ 官号建立、奖励活动和钓鱼式帖子均更晚。
```

叙事源审计：只找到 scanner 等非叙事观察；未找到有意义 Exact-CA 公开帖。

证据计数：公开提前 `fresh=0` / `standing=0` / 最近提前 `无公开提前信号`；+20% 前观测流 `9 买 / $3.7K / 9 钱包`；过滤后标记买入 `pre30=9/$4.1K`，`ascent=4/$1.7K`。

最佳支持机制：**前一区块资本先行**；置信度：**中**。

反证：波间仅隔数分钟，部分买入可能是首波延续而非独立二波信号；无技能合格钱包。

未知项：二波是否为同一资金组回拉；前一区块交易在真实节点上的传播延迟。

可直连证据（完整回执见 JSONL 账本）：

- [klausalphahq · ascent/scanner · 2026-08-09T22:13:30Z](https://x.com/KlausAlphaHQ/status/2086576633549316496)
- [csi888bsc · decay/account_created · 2026-08-09T22:26:30Z](https://api.fxtwitter.com/CSI888BSC)
- [csi888bsc · decay/post · 2026-08-09T22:35:11Z](https://x.com/csi888bsc/status/2086582090661781950)
- [BscScan · previous_block · 0x793b9480…](https://bscscan.com/tx/0x793b94804646224ba12d51895ff7605cb2a55d12deb22574acf20ca512d4c09d)
- [BscScan · previous_block · 0xe8bb9fa1…](https://bscscan.com/tx/0xe8bb9fa15403f24fbedebb4c6d775bbbc73b9e68a0240a3f2331331f3579adff)

### 波 3 — 至少一条经复核公开信号早于 +2%

行情：`08-10 16:45 UTC` 低点 → `08-11 18:45 UTC` 峰值，`4.57x`，峰值 close-FDV $587.6K；首个交易级 +2% `08-10 16:56 UTC`；1m +20% 边界 `08-10 18:02 UTC candle（严格提前截止 08-10 18:02 UTC）`。

```text
最早叙事源 ─ 经过前两波后项目身份和 Exact CA 已公开，第三波是既有 CSI 叙事续作。
├── 官号/头像 ─ 项目官号已有多个可直连状态；最近一次项目动作约在 +2% 前 55 分钟，时间上可作为新鲜催化。
├── +2% 前信号 ─ 3 个项目公开事件早于 +2%，其中 3,295 秒前的动作属于本波新鲜信号，可被在线订阅捕捉。
├── 链上点火 ─ +20% 前观测 35 笔、约 $2,635；没有过滤后标记聪明钱拉升买入。
├── 上升传播 ─ 官号在上升段继续奖励/领取类运营；独立 KOL 证据弱，更多是项目自传播。
└── 峰后内容 ─ 后续 phishing_lure 被明确排除，不能作为有效传播。
```

叙事源审计：只找到 scanner 等非叙事观察；未找到有意义 Exact-CA 公开帖。

证据计数：公开提前 `fresh=3` / `standing=0` / 最近提前 `54m55s`；+20% 前观测流 `35 买 / $2.6K / 31 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=0/$0`。

最佳支持机制：**项目运营 + 市场资金流**；置信度：**中**。

反证：项目动作与价格只具时间相关性；没有合格钱包或独立 KOL 交叉确认。

未知项：项目活动的真实参与转化；第三波主要买家身份。

可直连证据（完整回执见 JSONL 账本）：

- [x_project · closest-public-before-1.02/54m55s · 2026-08-10T16:01:22Z](https://x.com/i/status/2086845371565629815)
- [klausalphahq · historical_baseline/scanner · 2026-08-09T22:13:30Z](https://x.com/KlausAlphaHQ/status/2086576633549316496)
- [csi888bsc · historical_baseline/account_created · 2026-08-09T22:26:30Z](https://api.fxtwitter.com/CSI888BSC)
- [csi888bsc · historical_baseline/post · 2026-08-09T22:35:11Z](https://x.com/csi888bsc/status/2086582090661781950)
- [csi888bsc · historical_baseline/reply · 2026-08-10T00:42:50Z](https://x.com/csi888bsc/status/2086614213540081877)
- [csi888bsc · historical_baseline/post · 2026-08-10T01:58:20Z](https://x.com/csi888bsc/status/2086633212269224440)
- [csi888bsc · historical_baseline/post · 2026-08-10T16:01:22Z](https://x.com/csi888bsc/status/2086845371565629815)
- [csi888bsc · ascent/post · 2026-08-11T05:36:25Z](https://x.com/csi888bsc/status/2087050481818357973)

## SpaceXcoin

### 波 1 — 至少一条经复核公开信号早于 +2%

行情：`08-10 09:45 UTC` 低点 → `08-10 10:20 UTC` 峰值，`4.65x`，峰值 close-FDV $586.8K；首个交易级 +2% `08-10 09:48 UTC`；1m +20% 边界 `08-10 09:49 UTC candle（严格提前截止 08-10 09:49 UTC）`。

```text
最早叙事源 ─ ROME9998 在首波前直接发布 Exact CA 与 SpaceX 论点，是当前最早可直接核验的公开信号；未证实 SpaceX 官方关联。
├── 官号/头像 ─ 没有项目官号/头像动作证据。
├── +2% 前信号 ─ ROME9998 帖早于 +2% 1,732 秒（28分52秒），属于本波新鲜独立公开信号。
├── 链上点火 ─ 前 30 分钟过滤后买入 41 笔约 $7,283；+20% 前观测 36 笔约 $2,934；拉升段再有 14 笔约 $7,492。
├── 上升传播 ─ 其他 X/TG 账号在上升或后续接力；Bullish_Calls_BSC 原帖不可取，只保留二级回执。
└── 峰后内容 ─ 回撤与后续波段仍有持仓/喊话，不能重复算首波点火。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @ROME9998 · market_thesis · 创建后 16m08s。

证据计数：公开提前 `fresh=1` / `standing=0` / 最近提前 `28m52s`；+20% 前观测流 `36 买 / $2.9K / 24 钱包`；过滤后标记买入 `pre30=41/$7.3K`，`ascent=14/$7.5K`。

最佳支持机制：**新鲜公开论点 + 市场资金流**；置信度：**中高**。

反证：ROME9998 尚未通过稳定 KOL/钱包技能门禁；SpaceX 没有认可该 CA。

未知项：ROME9998 是否先于公开帖建仓；41 笔标记买入的协调关系。

可直连证据（完整回执见 JSONL 账本）：

- [x_exact · closest-public-before-1.02/28m52s · 2026-08-10T09:19:12Z](https://x.com/i/status/2086744159382372690)
- [ROME9998 · pre_trough/market_thesis · 2026-08-10T09:19:12Z](https://x.com/ROME9998/status/2086744159382372690)
- [dexeventcat · pre_trough/relay · 2026-08-10T09:25:57Z](https://x.com/DexEventcat/status/2086745859224429026)

### 波 2 — 至少一条经复核公开信号早于 +2%

行情：`08-10 11:00 UTC` 低点 → `08-10 12:40 UTC` 峰值，`2.78x`，峰值 close-FDV $873.2K；首个交易级 +2% `08-10 11:05 UTC`；1m +20% 边界 `08-10 11:06 UTC candle（严格提前截止 08-10 11:06 UTC）`。

```text
最早叙事源 ─ ROME9998 的首波论点仍站岗，二波前没有新的独立原创帖。
├── 官号/头像 ─ 仍无项目官号/头像动作。
├── +2% 前信号 ─ ROME9998 旧帖早于 +2% 6,399 秒；属于站岗信号，不是二波新爆点。
├── 链上点火 ─ 前 30 分钟过滤后 4 笔约 $2,358；+20% 前观测 85 笔约 $4,790；拉升段再有 10 笔约 $2,003。
├── 上升传播 ─ 首波形成的 SpaceXcoin 注意力与交易流推动二波，后续账号再接力。
└── 峰后内容 ─ 第二波回撤中的买入和喊话可能为第三波提供背景。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @ROME9998 · market_thesis · 创建后 16m08s。

证据计数：公开提前 `fresh=0` / `standing=1` / 最近提前 `1h46m`；+20% 前观测流 `85 买 / $4.8K / 56 钱包`；过滤后标记买入 `pre30=4/$2.4K`，`ascent=10/$2.0K`。

最佳支持机制：**旧叙事站岗 + 市场资金流**；置信度：**中**。

反证：没有二波新鲜公开催化；标记钱包未过点时技能门禁。

未知项：85 笔交易中首波持仓者占比；私域频道是否二次动员。

可直连证据（完整回执见 JSONL 账本）：

- [x_exact · closest-public-before-1.02/1h46m · 2026-08-10T09:19:12Z](https://x.com/i/status/2086744159382372690)
- [ROME9998 · historical_baseline/market_thesis · 2026-08-10T09:19:12Z](https://x.com/ROME9998/status/2086744159382372690)
- [dexeventcat · historical_baseline/relay · 2026-08-10T09:25:57Z](https://x.com/DexEventcat/status/2086745859224429026)
- [layla030906 · decay/market_thesis · 2026-08-10T13:00:07Z](https://x.com/layla030906/status/2086799756614041739)

### 波 3 — 至少一条经复核公开信号早于 +2%

行情：`08-10 20:25 UTC` 低点 → `08-11 12:05 UTC` 峰值，`5.98x`，峰值 close-FDV $742.7K；首个交易级 +2% `08-10 20:30 UTC`；1m +20% 边界 `08-10 20:31 UTC candle（严格提前截止 08-10 20:31 UTC）`。

```text
最早叙事源 ─ ROME9998 与 layla 的旧 SpaceXcoin 论点在第三波前站岗。
├── 官号/头像 ─ 无项目官号/头像证据。
├── +2% 前信号 ─ 2 个独立旧帖早于 +2%，分别约 7.5 小时和 11.2 小时前；没有本波新鲜公开信号。
├── 链上点火 ─ +20% 前观测 25 笔、约 $1,875；拉升段无过滤后标记聪明钱买入。
├── 上升传播 ─ layla 与其他账号在上升中再次喊话，属于放大而非提前点火。
└── 峰后内容 ─ 后续主要为市场跟随和叙事延续。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @ROME9998 · market_thesis · 创建后 16m08s。

证据计数：公开提前 `fresh=0` / `standing=2` / 最近提前 `7h30m`；+20% 前观测流 `25 买 / $1.9K / 18 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=0/$0`。

最佳支持机制：**旧叙事站岗 + 市场资金流**；置信度：**中低**。

反证：提前内容都是旧帖；没有合格钱包或官方关联。

未知项：第三波普通资金来源；不可取 TG 原帖是否曾有本波新消息。

可直连证据（完整回执见 JSONL 账本）：

- [x_exact · closest-public-before-1.02/7h30m · 2026-08-10T13:00:07Z](https://x.com/i/status/2086799756614041739)
- [ROME9998 · historical_baseline/market_thesis · 2026-08-10T09:19:12Z](https://x.com/ROME9998/status/2086744159382372690)
- [dexeventcat · historical_baseline/relay · 2026-08-10T09:25:57Z](https://x.com/DexEventcat/status/2086745859224429026)
- [layla030906 · historical_baseline/market_thesis · 2026-08-10T13:00:07Z](https://x.com/layla030906/status/2086799756614041739)
- [sol_jingou · historical_baseline/market_context · 2026-08-10T14:59:56Z](https://x.com/sol_jingou/status/2086829910858047897)
- [cz_yolo · historical_baseline/market_context · 2026-08-10T17:59:37Z](https://x.com/CZ_YOLO/status/2086875130098282709)
- [layla030906 · ascent/market_thesis · 2026-08-11T11:10:42Z](https://x.com/layla030906/status/2087134608412520900)

## 币安城

### 波 1 — 仅前一区块资金可普通确认

行情：`08-09 07:20 UTC` 低点 → `08-09 08:40 UTC` 峰值，`202.76x`，峰值 close-FDV $793.0K；首个交易级 +2% `08-09 07:24 UTC`；1m +20% 边界 `08-09 07:24 UTC candle（严格提前截止 08-09 07:24 UTC）`。

```text
最早叙事源 ─ “币安城”中文叙事的更早原始来源未核验；现有 Exact-CA 传播从链上启动后才出现。
├── 官号/头像 ─ 项目 X 账号不可用，没有可核验头像/官号动作。
├── +2% 前信号 ─ 公开面在 +2% 前为空；创建者地址前一区块买入，普通确认流理论可在跨阈值前看到。
├── 链上点火 ─ 创建者匹配钱包前 3 个区块、约 2 秒买入 $305.67；+20% 前 3 笔约 $626，拉升段过滤后 22 笔约 $8,986。
├── 上升传播 ─ guduchaobi1015、zhuilong888、Oxxiaoqi 均在 +2% 后、首峰前完成 CA 定盘和 Binance 中文叙事包装。
└── 峰后内容 ─ 首波回撤后这些帖子继续为二波提供站岗叙事，未见 Binance 官方认可。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @guduchaobi1015 · bare_call · 创建后 7m54s。

证据计数：公开提前 `fresh=0` / `standing=0` / 最近提前 `无公开提前信号`；+20% 前观测流 `3 买 / $626 / 3 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=22/$9.0K`。

最佳支持机制：**资本点火后社交放大**；置信度：**中高**。

反证：三位喊话者都不是 +2% 前信号；创建者买入不等于可复制聪明钱。

未知项：创建者与三位传播者是否协调；不可用项目账号曾发布什么。

可直连证据（完整回执见 JSONL 账本）：

- [guduchaobi1015 · ascent/bare_call · 2026-08-09T07:32:20Z](https://x.com/guduchaobi1015/status/2086354878222463331)
- [zhuilong888 · ascent/market_thesis · 2026-08-09T07:51:13Z](https://x.com/zhuilong888/status/2086359629999776017)
- [oxxiaoqi · ascent/market_thesis · 2026-08-09T08:14:20Z](https://x.com/Oxxiaoqi/status/2086365449709896107)
- [BscScan · previous_block · 0x89007d91…](https://bscscan.com/tx/0x89007d914e08aa78411ba9301ceee3e9cd0f234f334f80edfc53d5cc8cab18d7)

### 波 2 — 至少一条经复核公开信号早于 +2%

行情：`08-09 12:35 UTC` 低点 → `08-10 05:00 UTC` 峰值，`2.41x`，峰值 close-FDV $819.3K；首个交易级 +2% `08-09 12:40 UTC`；1m +20% 边界 `08-09 12:45 UTC candle（严格提前截止 08-09 12:45 UTC）`。

```text
最早叙事源 ─ 首波形成的“币安城”叙事和三个 Exact-CA 喊话账号在二波前完整站岗。
├── 官号/头像 ─ 仍无可核验项目官号或头像事件。
├── +2% 前信号 ─ 3 个独立公开帖早于 +2%，但全部是首波旧帖，并非二波新鲜爆点。
├── 链上点火 ─ +20% 前观测 59 笔、约 $4,343；拉升段仅 2 笔过滤后标记买入、约 $79。
├── 上升传播 ─ 旧喊话维持 CA 共识，随后交易流推动二次定价；未找到二波前的新 KOL。
└── 峰后内容 ─ 后续更多是市场复盘和板块归纳，不能解释二波开始。
```

叙事源审计：首个有意义 Exact-CA 帖可核验，但更早原创来源未解；首个有意义 Exact-CA 帖为 @guduchaobi1015 · bare_call · 创建后 7m54s。

证据计数：公开提前 `fresh=0` / `standing=3` / 最近提前 `4h25m`；+20% 前观测流 `59 买 / $4.3K / 39 钱包`；过滤后标记买入 `pre30=0/$0`，`ascent=2/$79`。

最佳支持机制：**旧叙事站岗 + 市场资金流**；置信度：**中**。

反证：没有本波新鲜公开事件；过滤后标记钱包金额很低。

未知项：59 笔交易的独立钱包与关联性；首波传播者是否在二波前私域再喊。

可直连证据（完整回执见 JSONL 账本）：

- [x_exact · closest-public-before-1.02/4h25m · 2026-08-09T08:14:20Z](https://x.com/i/status/2086365449709896107)
- [guduchaobi1015 · historical_baseline/bare_call · 2026-08-09T07:32:20Z](https://x.com/guduchaobi1015/status/2086354878222463331)
- [zhuilong888 · historical_baseline/market_thesis · 2026-08-09T07:51:13Z](https://x.com/zhuilong888/status/2086359629999776017)
- [oxxiaoqi · historical_baseline/market_thesis · 2026-08-09T08:14:20Z](https://x.com/Oxxiaoqi/status/2086365449709896107)

## 完整性与未解决风险

```text
本报告已覆盖 13/13 标的、32/32 有效波
├── 行情：5m 波段 + 交易级 +2%/+20% 跨越
├── 社交：98 个帖子×CA 人工语义、官号动作、TG 直连回执
├── 链上：RPC 区块位置、前一区块/同块边界、过滤后标记买入
└── 归因：主因、置信度、反证、未知项逐波齐全
```

仍不能保证私有 bundle、删除帖、封闭 TG/微信群或未索引内容的完整性；也不能从 13 个胜者反推假阳性、滑点或盈利。下一步在线系统若要追求原始事件 32/32 可见，必须接 BSC pending/Builder + 全新币创建流；若要追求可交易信号，则还必须在全市场失败样本上完成钱包/KOL 点时精度门禁。

权威机器账本：`bsc_week_wave_attributions.jsonl`；人工判断：`bsc_week_wave_attribution_reviews.jsonl`；完整性摘要：`bsc_week_wave_attribution_summary.json`。
