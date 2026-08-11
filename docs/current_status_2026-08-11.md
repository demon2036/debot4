# DeBot4 当前进展与交接

更新日期：2026-08-11（America/Los_Angeles）

## 一句话结论

DeBot4 目前是一套已经具备多源采集、叙事调查、证据复核和只读展示代码的“研究雷达”，但不是已经证明能赚钱的实盘交易系统。当前没有运行 DeBot4 采集器、事件触发 Grok、自动下单或看板服务，也没有真实 `buy MC -> 1h 最高 MC -> 可成交盈亏` 结果。

```text
当前状态
├── DeBot4 collectors：STOPPED
├── DeBot4 Grok worker：STOPPED
├── DeBot4 dashboard：STOPPED
├── 自动交易：不存在生产接线，也未运行
├── 本机 Grok2API：RUNNING，仅作为独立基础设施
├── 远程 Grok2API：RUNNING，仅监听远程 loopback
└── X/WARP 出口池：RUNNING，供后续 FxTwitter 并发请求使用
```

## 当前真实数据流

```text
外部信号
├── X / FxTwitter timeline
│   ├── 原创、回复、引用、文章、媒体
│   └── 独立 repost 轮询
├── Telegram
│   ├── 公开频道网页
│   └── 可选个人 session 实时流
├── DeBot 私有 API
│   ├── KOL
│   └── Smart Money
└── BSC 1h 市场异动榜
    └── exact CA 异动
        ↓
并发采集与不可变 checkpoint
        ↓
SQLite 优先级任务队列
        ↓
Grok 叙事研究
├── why-now / 原始来源 / 传播链
├── 竞争 CA
├── narrative leader / market leader
├── 阶段、反证和失效条件
└── X/TG 原文二次获取与身份核验
        ↓
exact-CA 门禁
├── 证据不足：WAIT
└── 证据充分：只形成研究结果
        ↓
SQLite research store + 只读看板
```

重要边界：上述生产数据流到“研究结果”为止，没有连接真实下单器。

## 已验证的内容

### 1. 代码与回归

- Python 生产代码和测试执行 300 行硬限制；本次已把超限的 app 装配测试按职责拆分。
- 本次最终全量回归：`243 passed`。
- X 出口池、并发 timeline、并发 repost、首次启动限量回放、DeBot/TG/市场任务入队、Grok 结构化结果和看板接口均有单元或集成级回归。
- 这些测试大部分使用受控 fake/fixture，证明规则与装配边界，不等于真实市场盈利验证。

### 2. X / FxTwitter

- 人物目录共有 112 条记录，其中 111 条当前允许 X timeline 监控，覆盖 BSC、Robinhood、Solana、Ethereum、Base、中日韩和全球英文圈。
- 数量不是质量证明：当前目录仍混有“已核验身份”“有具体历史帖子证据”和“只做候选观察”三种成熟度，尚未拆成正式 active/candidate/disabled 三层。
- X timeline 按人物等级设为 5–15 秒目标轮询，并支持最多 40 个并发 worker；这只是调度目标，实际发现延迟仍受 FxTwitter、网络和限流影响。
- 首次启动不会再无条件吞掉全部最新帖子：只回放最多 1 条、且必须在最近 5 分钟内，其余仅写 checkpoint。
- repost 路径已实现并发轮询。目前只有 `jtitordemon2036` 被设为 repost canary；尚未完成一次由真人转发触发、网页可见的端到端延迟验收。
- 公开 FxTwitter 不能稳定提供点赞事件；点赞监控尚未实现。
- 泛官方账号 `@X` 已从目录删除；`XDevelopers` 等泛产品源仍需在第二轮按“历史金狗/明确催化关系”重新审核。

### 3. 10 路出口池

2026-08-11 的新鲜复核结果：

- 本机 10/10 SOCKS 节点访问 FxTwitter 返回 HTTP 200。
- 远程机器经反向隧道使用同一池，10/10 访问 FxTwitter 返回 HTTP 200。
- 远程探测得到 10 个不同 IPv6 出口。
- 远程端口只绑定私有 Docker bridge；没有把 SOCKS 端口直接公开到互联网。
- 新增 `FxEgressPool`：线程安全 round-robin、有限次数 failover、每节点成功/失败计数和脱敏错误状态。

### 4. Grok2API

- 本机容器健康，健康接口返回 HTTP 200，监听 `:8000`。
- 远程容器健康，健康接口返回 HTTP 200，仅监听 `127.0.0.1:8340`。
- 远程数据库只读核对到 69 条 account credential / provider account 记录；这只证明已经导入，不代表 69 个账号此刻全部健康或有额度。
- 远程实际模型请求此前已跑通；本次交接只做健康复核，没有在系统暂停期间重新触发事件研究。
- DeBot4 当前不会自动消费 Grok：collector 和 Grok worker 都处于停止状态。

### 5. Telegram

- 已实现公开频道只读采集，以及可选的个人 Telegram session 实时采集适配器。
- 人工检查过 35 个已加入聊天；较有研究价值的候选包括 `Meetinggoldenca`、`A9Lesscall`、`crypto_onepiece1`、`Yndegen`、`LeoMaster_memes`。
- 当前人物注册表实际接线的是 5 个公开频道和 6 个 realtime 频道引用；35 个聊天并未全部进入生产监控。
- 尚未完成每个 TG 群的历史喊单、时间先后、CA、峰值 MC 和误报率审计。

### 6. 历史研究资料

- 已归档并结构化 69 条“北斗”历史叙事语料，区分方法论、前瞻、进行中和事后复盘。
- 已有因果回放候选，使用发帖后下一完整分钟的历史 OHLC 估算 1h 窗口；结果明确标注不是可成交报价，未包含滑点、税、gas、MEV 和历史深度重建。
- 已新增历史案例不可变数据模型，可记录 source/amplifier/posthoc、exact CA、时间、峰值代理和风险说明；模型尚未接入数据库与看板。

## 已做但不能夸大的能力

```text
“能采集”
└── 不等于“不会漏”

“Grok 能返回研究”
└── 不等于“叙事判断正确”

“历史 1m K 线显示上涨”
└── 不等于“当时能按该价格成交”

“目录里有 112 人”
└── 不等于“112 人都是高胜率车头”

“代码里存在估值/ledger/entry 模块”
└── 不等于“生产服务已经接入交易”
```

## 还没有完成的核心工作

### P0：赚钱基线闭环

```text
信号到达
├── 记录 source_at / detected_at / research_started_at
├── 完成叙事和 exact-CA 门禁
├── 决定 BUY 的同一时刻重新获取可成交报价与 MC
│   └── 禁止使用 30 秒前或最近一次采集缓存当 buy MC
├── 纸面成交或小额真实成交
│   ├── 滑点
│   ├── 税 / gas
│   └── 成交失败
├── 买后高频跟踪 1 小时
│   ├── 最高可成交 MC
│   ├── 最大回撤
│   └── 1h 结束可成交 MC
└── 形成不可修改的交易账本和策略版本
```

这条生产闭环尚不存在，因此现在没有胜率、期望值、盈亏比、漏单率或可验证收益。

### P0：人物与金狗证据库

- 把 112 条人物记录拆成 `active_verified`、`research_candidate`、`disabled_no_evidence`。
- 每个 active 人物必须记录：关联币、chain、CA、原帖时间、创建时间、角色、触发前后位置、峰值 MC、证据 URL 和是否事后分析。
- 需要纠正或复核剩余泛官方账号、Yeon 的个别证据 ID，以及只做 profile review、没有具体案例的候选。
- 已确认的 BSC 样本线索包括齐天大圣、PIZZA/House、MarsCoin、GME、Just a Jacket、MEMEFI、FSTOCK、TST/Broccoli、币安人生；当前还只是研究线索，不是完整可审计案例库。

### P0：历史覆盖

- BSC 最近 1 年突然拉升项目尚未系统补齐。
- Robinhood 最近 3 个月数据尚未补齐；现有本地 Robinhood 数据只覆盖 2026-07-10 至 2026-07-12，不能代表 3 个月。
- 需要独立用 1h gainers 真值集检查漏报，而不是只看系统自己发现的币。

### P1：运行与展示

- `serve.py` 目前会同时启动 collectors 和 Grok worker；尚无安全的 dashboard-only 模式。
- 看板尚未展示历史金狗案例、KOL-金狗关系、TG 来源、10 路出口健康、端到端延迟和明确暂停状态。
- Tunnel Host/Origin 白名单尚未适配外部域名，因此当前没有可交付的公网看板 URL。
- 远程机器本次只同步代码，不启动 DeBot4 服务。

### P1：真实 SLA 与效果验收

- 尚未连续运行 24 小时并建立人工真值集。
- 尚未测出关键人物事件的 p50/p95 发现延迟、Grok 开始延迟和研究完成延迟。
- 尚未计算 BSC/Robinhood 金狗召回率、错误 CA 率、WAIT 率和假阳性率。
- 尚未完成慢 Grok 请求下关键人物事件不被阻塞的真实压力测试。

## 下一轮正确顺序

```text
1. 案例真值层
├── 补齐 BSC 1 年 + Robinhood 3 个月
└── 固化 source / amplifier / posthoc 证据

2. 人物层
├── active_verified
├── research_candidate
└── disabled_no_evidence

3. 运行层
├── dashboard-only
├── 延迟指标
└── 暂停/运行状态清晰展示

4. 基线交易层
├── decision-time live quote / MC
├── paper fill
├── 1h executable peak tracking
└── 不可变结果账本

5. 验收层
├── 24h 人工真值
├── gainers 漏报审计
└── 只根据真实数据决定是否进入小额实盘
```

## 仓库与部署

- GitHub：`demon2036/debot4`，PRIVATE，默认分支 `main`。
- 本机仓库：`/home/john/debot4`。
- 远程代码目录：`/opt/debot4`。
- 本次交付要求：本机、GitHub `origin/main` 与远程 `/opt/debot4` 的 HEAD 一致；远程只拉代码，不启动 DeBot4。
- 凭证、cookies、Telegram session、SQLite 运行库和日志均被 Git 忽略；仓库只提交无密码的出口拓扑。

## 安全提醒

VPS 密码曾在聊天中明文出现。代码同步完成后应立即轮换该密码，并继续使用 SSH key；仓库和本文都不保存或复述该密码。
