# 远程 KOL 与钱包研究冻结审计

- 冻结时间：2026-08-12
- 数据源：远程 `/opt/debot4/research/golden_dogs/`
- 用途：判断当前研究量是否足以支持自动买入；不是收益宣传，也不是 KOL 排名。

## 已取得的数据量

```text
BSC 最近一年 DeBot launch-source 快照
├── universe tokens             3,071
├── market candidates          243
├── provider-tagged buy tokens 125
├── RPC clean-buy tokens       122
├── pre-peak RPC clean-buy     112
├── qualification outcomes
│   ├── REJECT                  46
│   ├── WAIT                    90
│   └── PASS                    0
└── source_scope_complete       false

Robinhood 最近三个月 DeBot launch-source 快照
├── universe tokens             4,615
├── market candidates          349
├── source_scope_complete       false
└── provider/chain closure      false

X / 钱包交叉证据
├── candidate accounts          1,603
├── manual role reviews         87
├── wallet-bound accounts       202
├── verified status-CA pairs    774
├── unique accounts in pairs    446
├── pre-peak pairs              82
├── post-peak pairs             692
├── exact author-wallet buys    17
└── qualification
    ├── REJECT                  214
    ├── WAIT                    560
    └── PASS                    0
```

## 能否支撑 BOT 拉升检测

```text
可以支撑
├── 建立候选账号与钱包队列
├── 识别峰前/峰后 exact-CA 帖
├── 核验 BSC Swap 和 provider 标签
├── 发现 BOT 第一波传播与 CA 选择者
└── 为新的爆点建立搜索起点

暂时不能支撑
├── 自动判定哪个账号是长期高胜率车头
├── 证明某个发帖者就是对应买入钱包
├── 从头像变化直接选择唯一 BOT CA
├── 把回顾性样本倍数当成实盘胜率
└── 自动买入；当前所有闭环结果仍为 0 PASS
```

已人工复核的 21 个信号对只覆盖 16 个 token；其中第一条复核帖后达到 2x 的有 12 个、达到 5x 的有 5 个、1 小时内到峰值的只有 3 个。该集合是从已上涨样本倒推出来的选择性样本，不能作为胜率分母。

## BOT 新增候选

```text
第一波 2026-08-09
├── mstzera 绑定钱包          +60s，约 $1,185；稳定身份通过，2 个 eligible 样本
├── Stigman__ 绑定钱包        +69s，约 $415；10 个 eligible / 5 个 pre-peak
├── cryptomoon520 绑定钱包    +94s，约 $348；高频套利特征，明确降级
├── @false2z                  +165s，峰前区分主 CA 与开发者费竞品
├── rawrstarxdd 绑定钱包      +194s/+206s，两次约 $296；5 个 eligible 均 pre-peak
├── 0xfanfanfan 绑定钱包      +255s，约 $148；4 个 eligible / 2 个 pre-peak
├── @9999btcname              +740s，峰前但已明显上涨，属持仓传播
├── @CryptoBitxin             峰后 exact-CA 帖，只算 posthoc
└── @munburanketto            峰后 listing/vote 传播，只算 posthoc

第二波 2026-08-11
├── @sizzlezzzzzzzzz          波前 exact CA + 预期 Elon reveal
├── @bot 新头像               -0.042s，真正的身份激活爆点
├── @bot Banner               +51s，第二个身份确认
└── @bot 官方帖子             +1,325s，晚于启动 22:05、晚于记录峰值 19:05
```

`@false2z`、`@sizzlezzzzzzzzz`、`@9999btcname` 以及上述四个保留的钱包绑定账号已进入审计目录，但全部只有 `PROPAGATE` 权限；不具备绑定 CA 或直接放行交易的权力。`cryptomoon520` 不进入优先监控，因为“早买一次 + 高频交易”不足以证明选择性。

2026-08-12 的远程有限关系快照显示，当前 `@bot` 关注 `@elonmusk`、`@grok`、`@SpaceX`、`@SpaceXAI`；这四个账号当前也关注 `@bot`。该快照只能证明调查时的网络结构，不能倒推出 2026-08-11 的新增关注时间。

## 下一轮升级门槛

每个 KOL/钱包必须补齐：所有可观察喊单分母、exact CA、发帖时间、创建时间、当时可成交 MC、峰值与时间、亏损样本、钱包归属证据、是否峰前、是否存在更早来源。没有完整分母就只能留在 `research_candidate`。
