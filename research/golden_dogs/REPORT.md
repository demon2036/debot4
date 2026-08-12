# BSC 一年 / Robinhood 三个月金狗、KOL 与 X 证据审计

数据冻结日：2026-08-12 UTC。本报告中的“金狗”仅指研究候选，不是收益或交易建议。

## 当前结论

```text
固定 UTC 7 天窗口
├── BSC：2025-08-12 ~ 2026-08-12
│   ├── DeBot launch-source universe：3,071 exact CA
│   ├── 市场历史完整：3,059；无历史：12
│   ├── 窗口峰值 MC/FDV >= $500K：243
│   ├── 其中 DeBot 聚合 max_kols > 0：136（只算待核线索）
│   └── GMGN + BSC RPC 闭环
│       ├── 有窗口内 GMGN tagged buy：125
│       ├── RPC swap 验真且钱包无已知 wash tag：122
│       ├── 其中峰值前买入：112
│       └── 最终门禁：0 PASS / 90 WAIT / 46 REJECT
└── Robinhood：2026-05-12 ~ 2026-08-12
    ├── DeBot launch-source universe：4,615 exact CA
    ├── 市场历史完整：4,561；无历史：54
    ├── 窗口峰值 MC/FDV >= $500K：349
    └── 其中 DeBot 聚合 max_kols > 0：103（尚未完成 provider/链上闭环）
```

为什么 BSC 暂时 0 PASS：122 个候选已证明确有 GMGN 标记买入和真实 BSC swap，但
`wash_or_circular_trading` 等操纵检查没有完整历史证据。缺失数据必须保持 WAIT，不能把
“链上买过”偷换成“盘子干净”。46 个 REJECT 包含完整历史中无干净买入或已发现风险者。

这些数字是 DeBot 当前暴露的 launch-source 快照下限，不是 BSC/Robinhood 全链全集。
当前 BSC 达标候选实际集中在 2026-05-12 以后；这只能说明该快照早期没有保留下达标行，
不能说 2025-08 至 2026-05 没有金狗。

## 权威口径

```text
金狗资格
├── 市场门槛：代币创建所在固定 7 天窗口内峰值 MC/FDV >= $500K
├── KOL 买入：DeBot 或 GMGN 的真实买入事件
│   ├── exact wallet + transaction hash
│   └── BSC 候选再由 RPC 验证 token buy swap
├── 操纵门禁：关联资金、集中持仓、wash/circular 缺一项即 WAIT
└── 因果标签（不改变金狗资格）
    ├── 峰值前买入：可研究早期信号
    └── 峰值后买入：不是因果命中，但仍可能满足“有 KOL 买过”
```

X/Twitter 是本轮主线。KOL 可以没有公开钱包；账号身份、原帖和上涨时序与钱包归因分开。
小号可能提前几天埋伏，所以单次提前买入只进入候选，多个独立 exact-CA 的重复命中增强
归因可信度，但仍不代替公开 X 身份、帖子语义和完整交易分母。

## X / 中文 KOL 证据

```text
已独立拉取的 X 证据
├── 中文 KOL 目录：27/27 主页稳定 ID 匹配，4/4 来源帖可重取
├── Grok 中文圈线索：640 个 direct-status lead
│   ├── 639 个作者身份与原帖独立验证
│   └── 1 个 author mismatch 已拒绝
├── exact CA join：123 次正文地址提及，107 个 CA
│   ├── 命中达标市场：31 个 status-CA pair / 20 个代币
│   └── 时序：4 个 pre-peak，27 个 post-peak
└── GMGN/RPC 买入钱包反推账号
    ├── 228 个去重钱包
    ├── 207 个 X 主页可拉取
    ├── 193 个钱包资料与稳定 X ID 一致
    ├── 171 个钱包买过 >=2 个独立达标 CA
    └── 141 个钱包在 >=2 个达标 CA 峰值前买过
```

“verified X”只证明账号和该账号确实发过该帖，不自动证明它是 KOL、原创喊单或因果来源。
例如 `BscKOLScanner` 是扫描器，`sol_jingou` 的部分内容是峰后汇总；这类账号不能和主动
喊单 KOL 混为一谈。泛产品账号 `@base`、`@XDevelopers` 已从监控目录删除；CZ、何一、
Musk 这类可能直接制造叙事催化的账号保留。

“深大高财生/深大高材生/深大”已稳定绑定到：

- X：<https://x.com/GCsheng>
- stable user ID：`1344963706657017858`
- 显示名：`深大高财生.milady`
- 已归因钱包：`0x51fbb0b8164231c116acdce55db3d5c0d9650987`
- 归因来源：<https://x.com/lookonchain/status/1975782365650952370>

其旧 exact-CA 帖 `0x61a619...4444` 对应币峰值约 `$122.5K`、`max_kols=0`，不是本口径
金狗；身份仍保留。另一个 Golden Age 案例 `0x259530...7777` 有完整 GMGN/RPC 买入：
该钱包于 2026-07-29 07:35:09Z 买入约 `$393.64`，tx
`0xb5a07488bf96a8ccd2faed78fbc8b4fc8437428424868fab031f166fd9b00d6f`，代币随后在
2026-07-30 13:20Z 达约 `$10.03M`。市场、买入、RPC 和时序通过，操纵门禁仍 WAIT。

## Grok 地毯扫描

- 一年周扫：53 个固定窗口 × 3 个角度，共 159/159 任务至少成功一次。
- 中文 KOL 搜索：35/35 唯一任务成功。
- exact-CA 主线：对 243 个 BSC 达标 CA 分 108 个双通道任务，搜索原帖与身份/钱包归因；
  结果写入可重启 journal，再由 FxTwitter 独立重取。

Grok 只负责找线索。它曾漏掉已知 GCsheng 原帖，也曾给出作者不匹配，因此任何回答都不
直接进入资格结果。

## 聪明钱包边界

GMGN 7 日 KOL rank 的 100 行里，73 行带 X，70 行可完整核验，60 行完成钱包/X 绑定；
32 行仅凭 7 日交易频率就属于明显高频，排除出聪明钱包信号。利润和 provider win rate
不用于排名。其余钱包仍需完整期间活动、买过的所有代币和每个结果；分母不完整一律 WAIT。

## 仍未完成

- DeBot launch-source 不是全链池历史，尚无独立全链 1h-gainers 真值集，不能报告召回率。
- BSC 90 个 WAIT 尚需补齐 holder/funder/wash/circular 历史；不能宣称已找到合格金狗全集。
- Robinhood 349 个市场候选尚未完成真实 provider KOL 买入和链上交易闭环。
- 243 CA 的 Grok exact-CA 扫描及独立 X 重取正在完成；帖子还需按 own call、catalyst、
  scanner、project、repost、post-peak recap 人工/证据分类。
- 228 个钱包的完整交易分母和全部买入结果未重建，不能给聪明钱包胜率。
- OHLC high 与当前 supply 计算的是历史代理，不包含流动性、税、gas、滑点和 MEV，不能
  表示可实现收益。

机器可读证据见 `coverage.json`、`bsc_gmgn_audit_summary.json`、
`bsc_gmgn_qualification.jsonl`、`bsc_audit_wallet_x_verified.jsonl`、
`gmgn_bsc_kol_rank_x_verified.jsonl` 和对应 SHA-256 收据字段。
