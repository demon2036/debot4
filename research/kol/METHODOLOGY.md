# KOL 发现与核验方法

这份方法用于避免再次漏掉 `Yeon / @yeonwoo1102`，也避免 Grok 把真实 tweet ID 错挂到另一个账号路径后被系统误收录。

```text
候选发现
├── 精确 handle：@yeonwoo1102，而不是只搜显示名 Yeon
├── 别名：Yeon / yeonwoo / 韩文名 / 中文称呼
├── 稳定 user ID：handle 改名后仍可识别同一账号
├── 关系图：被谁回复、引用、共同传播、TG 互相导流
├── 地区桶：中国 / 韩国 / 日本 / 美国 / 全球
└── 生态桶：BSC / Solana / Base / Ethereum / Robinhood / X
```

此前漏掉 Yeon 的根因不是“没有这个人”，而是发现方法只依赖显示名和泛关键词。显示名短、可重复、跨语言，并且 X 搜索结果会被大号和近期热帖淹没。以后以 handle、稳定 ID、别名和关系图为主键，Grok 只能提出候选，不能直接写入信任目录。

```text
候选入库硬门禁
├── URL 路径 handle == 候选 handle
├── FxTwitter 返回的真实推文作者 == 候选 handle
├── 推文 author ID 非空
├── FxTwitter profile handle == 候选 handle
├── profile user ID == 推文 author ID
├── 身份/地区/链有公开资料或本人原帖证据
├── 项目方、付费推广、持仓冲突写入 risk_notes
└── 任一步失败 -> 不进入自动监控目录
```

Grok 的职责是搜索和扩展关系图，不是认证。2026-08-10 的实测中，Grok 曾把 `theunipcs` 的真实 tweet ID 拼到 `CryptoKaleo` 路径，也把同一韩国账号的 tweet ID 归给多个不同候选。`actor_evidence.py` 因此要求 URL、推文、资料页三方身份一致。

```text
监控用途
├── agenda / ecosystem authority：可触发“主动叙事调查”
├── domain expert：可提供解释和反证，不能自动绑定 CA
├── propagation KOL：只作为传播线索，不能证明官方背书
└── paid/project-affiliated：保留观察价值，但必须降权并标风险
```
