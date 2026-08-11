# robinhoodwallet 架构拆解与 DeBot4 对照

研究对象：`/home/john/debot5/robinhoodwallet`，提交
`9288f6c46c1cdd8aae5e9071498416cdbbd68dfc`。

这份文档只记录源码能够证明的事实。该项目是监控、研究和看板系统，
不是交易执行器；仓库中没有发现签名、私钥加载、交易发送或订单执行路径。

## 1. 总体结构

```text
外部信号
├── X 账号主页
│   └── 500ms 快速轮询 -> HTML 解析 -> pending/seen 去重
├── Telegram 个人账号
│   └── Telethon NewMessage 推送 -> 多会话合流
├── 飞书授权账号
│   └── 5 个会话每 2s 并行拉取 -> 11 个人物归因
├── DeBot / 链上 RPC
│   └── 钱包、代币、池子和交易事件
└── 本地 SQLite
    ├── 原始事件与动作
    ├── 钱包画像与人工标注
    ├── 代币元数据与提醒状态
    └── 分析任务和 JSON 快照

展示
├── 主 Robinhood 服务：默认 127.0.0.1:18118，提供网页
├── BSC 服务：默认 127.0.0.1:18122，只提供 API
├── 飞书桥：默认 127.0.0.1:18124，SSE 推送
└── Telegram viewer：默认 127.0.0.1:8765，只读网页
```

## 2. X / Twitter 如何监控

权威代码：

- `src/social/xProfileMonitor.js`
- `src/social/service.js`

```text
配置的 fast handles
└── service 每 500ms 调用 pollFastXProfiles
    └── XProfileMonitor.pollOnce
        ├── 每个账号独立 in-flight 状态
        ├── 总并发限制，默认 2，可配置 1..8
        ├── GET https://x.com/{handle}
        ├── 3s 默认超时 + 指数退避 + 响应体大小保护
        ├── 从 HTML/内嵌数据提取多条 post
        ├── seen：已经确认消费的 post
        └── pending：已经发现但尚未确认消费的 post
            └── 上游处理成功后 confirm(handle, tweetIds)
```

优点：

- 快速通道和普通社交源分开，重要人物不被慢任务堵塞。
- `pending -> confirm -> seen` 避免“采到即丢”；下游失败可以重试。
- 每账号隔离退避与 in-flight，单一账号失败不会拖死全部账号。
- 不依赖浏览器或 CDP。

问题：

- 依赖 X 网页 HTML 和大量手写解析规则，页面结构变化时很脆弱。
- `src/social/service.js` 同时承担太多来源和业务编排，耦合过高。
- handle 是主要身份键；DeBot4 还需要稳定 user ID 防改名和冒充。

DeBot4 采用：

```text
actor catalog（handle + stable user ID + region + chains + role）
└── 高优先级人物独立快速队列
    └── FxTwitter / 直接 API 取结构化 post
        ├── 验证 author ID
        ├── 原帖不可变落库
        ├── pending/ack 语义
        └── 进入叙事调查，不直接等同于买入信号
```

保留它的快速通道、并发隔离、退避和确认语义；不复制其 HTML 解析器。

## 3. Telegram 如何监控

权威代码：

- `telegram/viewer.py`
- `telegram/README.md`

Telegram 采集本身不是轮询。它使用个人 Telethon session 登录并订阅
`events.NewMessage()`：

```text
本机个人 Telegram session
├── 启动时读取已授权 dialogs
├── 用户选择群组/频道
├── 拉取所选会话历史并按时间合并
└── Telethon NewMessage 实时推送
    └── MultiChatController
        ├── 标准化 message / sender / reply / media
        ├── 合并进只读消息流
        ├── 异步翻译
        └── CA 提醒与发送者规则

本地 viewer
└── ThreadingHTTPServer :8765
    ├── 浏览器取本地合并结果
    ├── translation cache SQLite
    └── CA alert SQLite
```

关键点：

- 新消息由 Telegram 长连接推送，延迟不受前端 2 秒刷新限制。
- Telethon session、API 凭证和翻译密钥都应留在仓库外。
- viewer 是只读：不发送、不编辑、不删除 Telegram 消息。
- 其 `viewer.py` 超过 3700 行，把客户端、缓存、HTTP、翻译、提醒和 UI
  状态混在一起，不适合作为 DeBot4 的代码模板。

DeBot4 应保留事件模型，按职责拆开：

```text
telegram.client       # 只管理 Telethon session 与订阅
└── telegram.parser   # 原始 update -> 不可变标准消息
    └── narrative.telegram_trigger  # 人物/频道/CA/叙事触发
        ├── research queue
        ├── raw evidence store
        └── independent alert/dashboard consumers
```

## 4. 飞书如何监控

权威代码：

- `feishu-bridge/src/config.js`
- `feishu-bridge/src/lark-client.js`
- `feishu-bridge/src/monitor.js`
- `feishu-bridge/src/server.js`

```text
VPS 已授权 lark-cli 用户身份
└── 5 个固定飞书 chat ID
    └── 每 2s 并行 GET /open-apis/im/v1/messages
        ├── 按 message ID 去重
        ├── 按时间排序
        ├── 每个人最多保留 10 条
        └── 说话人归因
            ├── 独立会话：全部消息属于该人物
            ├── 昵称前缀匹配
            ├── tenant key 匹配
            └── 引用消息中的 speaker 匹配
                └── SSE -> 主网站
```

源码配置的 11 个人物：Sen、Lasercat、MrDQ、大齐、luck(发财版)、LU、
Chenpepe、CryptoD、王小二、0xSun、0xAce。

这里的 2 秒是飞书 API 轮询间隔，不是 Telegram 消息延迟。飞书授权保存在
VPS 私有 `.lark-cli` 目录，公开 clone 不包含可直接使用的授权。

DeBot4 可以复用“会话来源 + 说话人匹配器 + 消息 ID 去重 + SSE”模型，
但每种匹配规则必须是独立配置，不把人物判断写死在采集循环中。

## 5. 数据库如何构建

公开快照：`database/robinhood-public.sqlite.gz`。源码使用 Node
`DatabaseSync`，主库启用：

```text
PRAGMA journal_mode = WAL
PRAGMA synchronous = NORMAL
```

公开快照中的主要表和当时记录数：

| 表 | 记录数 | 作用 |
| --- | ---: | --- |
| `actions` | 7,790 | 买卖/转账动作；`tx_hash + log_index` 唯一 |
| `monitor_events` | 7,854 | 钱包与代币监控事件；链上位置去重 |
| `wallet_summaries` | 1,149 | 钱包评分和分析 JSON 快照 |
| `wallet_annotations` | 333 | 人工别名、标签、分类覆盖、监控层级 |
| `monitor_token_metadata` | 1,128 | 监控代币元数据 |
| `monitor_token_alerts` | 59 | 每个 token 的提醒状态 |
| `tokens` | 58 | 核心代币记录与 payload |
| `jobs` | 29 | 后台分析任务及状态 payload |
| `metadata` | 9 | 库级元数据和版本信息 |
| `monitor_bark_targets` | 0 | 公开快照删除了私有目标，但保留 schema |

它不是完整规范化的交易账本，而是“确定性索引列 + 灵活 JSON payload”的
监控/研究缓存：

```text
链上原始事件
├── actions / monitor_events       # 可重放、可去重
├── tokens / token_metadata        # 实体缓存
├── wallet_summaries               # 机器分析快照
├── wallet_annotations             # 人工覆盖层
├── jobs                            # 长任务恢复点
└── alerts                          # 防重复发送状态
```

另外可通过 `ATTACH DATABASE` 挂载共享钱包库和 Bark 目标库。公开数据库可以
作为 schema、事件去重和快照设计参考，不能替代私有实时数据源。

DeBot4 数据库应增加朋友项目没有覆盖完整的叙事证据链：

```text
raw_signal
├── source / source_event_id / observed_at
├── exact author stable ID
├── exact post/message content hash
└── immutable raw payload

narrative_research
├── earliest source
├── causal actor and post type
├── exact CA + competing CAs
├── propagation path
├── invalidation conditions
└── verdict: READY / WAIT / REJECT

paper_execution
├── decision_at
├── decision-time quote and MC       # 不能用 30 秒前采集值
├── simulated fill
└── 1h maximum MC / return
```

## 6. BSC 看板是什么

```text
主服务 :18118
├── 提供 public 网页看板
└── /internal/debot/request 给 BSC bridge 使用

BSC 服务 :18122
├── 独立 BSC monitor RPC
├── 独立 holder RPC
├── holder / token / wallet 分析 API
└── servePublic: false
```

因此，单独拉起 `src/bsc/server.js` 只会得到 BSC API，不会得到一个独立 BSC
网页。要看 UI，需要同时运行主 Robinhood 服务，并让网页查询 BSC API。

## 7. clone 后能否直接使用

```text
公开 clone
├── 可以：安装依赖、跑测试、研究代码、读取公开 SQLite 快照
├── 条件具备后可以：启动本地 API / 主网页
└── 不能直接获得朋友生产效果
    ├── 缺少其 Telegram session 和选中频道
    ├── 缺少飞书用户授权和固定会话权限
    ├── 缺少生产 RPC / DeBot bridge / 私有监控目标
    └── 公开数据库对私有目标做了脱敏
```

不能把朋友的私有 session 或授权文件复制进仓库；DeBot4 必须使用本机自己的
Telegram session、自己的 API 凭证和独立数据库。

## 8. 是否包含交易

结论：没有。

```text
已存在
├── 识别链上 buy / sell / transfer
├── 钱包和代币画像
├── 监控事件与提醒
├── 社交信息流
└── 看板展示

未发现
├── 私钥或 signer 管理
├── approve / swap 构造
├── eth_sendTransaction / eth_sendRawTransaction
├── 成交确认与 nonce 管理
└── 仓位、止损、退出执行器
```

它可以作为“信号采集与研究底座”的参考，不能当作可交易系统。

## 9. DeBot4 抄什么，不抄什么

```text
采用
├── X 高优先级快速通道
├── 每账号并发隔离与指数退避
├── pending -> ack -> seen 的可靠消费
├── Telegram NewMessage 推送
├── 飞书 speaker matcher 配置模型
├── 原始事件唯一键与 WAL SQLite
└── 私有凭证全部仓库外存放

改进
├── handle + stable user ID 双身份
├── 主动名人发言与被动价格/KOL 异动两类触发
├── 人物身份、地区、chain、因果权限和传播权限分开
├── 原帖 -> 叙事 -> exact CA -> 竞争 CA 的完整证据链
└── 决策时重新取实时 MC/报价并记录 1h 最大 MC

拒绝复制
├── X 大型手写 HTML 解析器
├── 3700+ 行 Telegram 单体文件
├── 巨型 social service 万能模块
├── 把传播账号互动误判为代币背书
└── 把公开数据库误当实时生产数据
```
