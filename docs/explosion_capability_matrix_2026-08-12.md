# 爆炸叙事能力矩阵

- 审计时间：2026-08-12
- 运行约束：本文只描述已存在代码和有限冒烟能力；常驻采集、Grok 事件触发和交易均保持停止。

```text
监控面
├── X 时间线/转发                 已有真实 FxTwitter 适配器
├── 身份变化                     已有真实 Profile/图片适配器与快照 Diff
├── 生态权威关系                 已有完整 following 分页适配器与快照 Diff
├── 产品与代码提前泄露           已有官网/Sitemap 镜像、文档/GitHub HTTP 适配器
├── 原作者/IP 确权                已有领域事件规则；缺稳定原作者注册表与主动采集器
├── 权威钱包动作                 已有链上语义规则；缺经证据审核的钱包注册表与常驻扫描器
├── 现实世界源事件               已有领域事件规则；缺可信新闻/活动数据源适配器
├── 分发入口打开                 已有领域事件规则；缺交易所/钱包/Launchpad 状态适配器
├── 风险突然解除                 已有状态转换规则；缺争议与修复证据适配器
└── 正统 CA 胜出                 已有竞争集纯规则；缺跨模块证据聚合与持有人迁移适配器
```

## 当前可以真实运行的三条路径

### 1. X 身份变化

```text
FxTwitter Profile API
├── 名称 / Bio / 官网 / 认证 / 位置
├── 头像 URL -> snowflake 来源时间
├── Banner URL -> Unix 来源时间
└── URL 变化时下载图片并记录 SHA-256
    ↓
Profile 前后快照
    ↓
identity_change ExplosionEvent
```

限制：公开 FxTwitter Profile 当前没有可靠的置顶帖和组织关联字段；handle 改名后还需要按稳定 user ID 恢复新 handle 的数据源。

### 2. 权威关系变化

```text
BOT 权威网络稳定 user ID
├── @bot
├── @grok
├── @X
├── @SpaceXAI / @xai
├── @elonmusk
└── @SpaceX
    ↓
完整 following 游标分页
    ↓
新增/取消关注 Diff
    ↓
ecosystem_authority ExplosionEvent
```

限制：只有建立第一份关系快照后，第二份快照才能判断新增/取消关注；旧历史快照缺失时不能倒推出发生时间。

### 3. 产品与代码提前泄露

```text
公开官方资源
├── x.ai/sitemap.xml            经只读镜像抓取，证据 URL 保留官方地址
├── x.ai/bot                    经只读镜像抓取，证据 URL 保留官方地址
├── docs.x.ai/overview          直连
└── api.github.com/orgs/xai-org/repos  直连
    ↓
内容哈希 + 标题 + 关键词 + exact CA + 新路径
    ↓
前后快照 Diff
    ↓
product_leak ExplosionEvent
```

限制：X 专用 WARP 出口实测不能稳定读取这些站点，所以没有复用 X 出口池；镜像内容必须回查官方 URL。公开网页没有来源自带变更时间时，`occurred_at` 只能等于系统首次看到时间；内容哈希报警也不代表已绑定任何社区代币。

## 交易门禁

```text
任何爆点
├── 只触发调查，buy_eligible=false
├── exact CA 未绑定 -> WAIT
├── 竞争 CA 未解决 -> WAIT
├── 操纵与可成交性未通过 -> WAIT/REJECT
└── 仅全部通过后
    ├── 决策瞬间重新读取 MC
    ├── 请求真实可执行报价与滑点
    ├── 记录是否实际成交
    └── 追踪买入后 1h 最高 MC 与净收益
```

BOT 当前仍为 `WAIT`：头像变化可以很早识别叙事，但官方身份并未发布或绑定 `0xbcad...7777`，候选 KOL/钱包也没有完整历史分母。
