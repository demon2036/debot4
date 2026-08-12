# 远程爆炸叙事部署与有限验证

- 日期：2026-08-12
- 远程独立代码目录：`/opt/debot4-explosion-20260812`
- 远程状态目录：`/var/lib/debot4/explosion-baseline`
- 原目录：`/opt/debot4`，已有用户修改，本轮没有清理、覆盖或切换分支。

## 部署边界

```text
远程机器
├── /opt/debot4                         原有脏工作区，保持原样
├── /opt/debot4-explosion-20260812      本轮只读研究与有限验证代码
├── /var/lib/debot4/explosion-baseline  私有快照与事件状态
└── /root/.config/debot4/credentials
    └── debot_cookies.json              仓库外、0600、内容不进入日志或 Git
```

DeBot Cookie 已经通过仓库外私有路径接入远程，并完成一次有限只读鉴权检查。Git 忽略凭证、状态、数据库和日志；文档不保存凭证内容。

## BOT 有限验证结果

```text
身份路径
├── 7/7 目标 Profile 请求成功
├── 名称、Bio、网址、认证、头像和 Banner 字段可解析
└── 第二次相同快照：0 个新事件，证明 Diff 幂等

关系路径
├── 7/7 目标完整 following 游标成功
├── @bot 当前关注 Elon、Grok、SpaceX、SpaceXAI
├── 四者当前也关注 @bot
└── X 与 xAI 当前未关注 @bot；仅为 2026-08-12 快照，不是历史发生时间

产品路径
├── 4/4 公开资源读取成功
├── 当前产品标题：Grok Bot: A new kind of colleague
├── 当前官网：x.ai/bot
├── 页面未出现 BSC exact CA
└── 第二次相同快照：0 个新事件
```

产品状态库中仍有 7 条早期静态基线产生的历史事件，属于旧基线噪声；本轮第二次扫描没有新增事件，不能把那 7 条解释为实时泄露。

## 研究量与交易结论

```text
BSC 审计
├── 3,071 个 universe token
├── 243 个市场候选
├── 122 个 RPC clean-buy token
├── 112 个 pre-peak clean-buy token
└── 0 PASS / 90 WAIT / 46 REJECT

X/钱包交叉
├── 774 个 status-CA pair
├── 82 个 pre-peak pair
├── 17 个 exact author-wallet buy
└── 0 个达到自动买入完整门槛
```

因此当前数据足以支撑“发现、排序、调查和回放”，不够支撑自动买入。BOT 的头像变化能够触发快速调查，但没有官方 exact-CA 绑定，最终仍必须 `WAIT`。

## 运行状态

```text
DeBot4 collector             STOPPED
DeBot4 dashboard             STOPPED
DeBot4 trader                STOPPED
事件触发 Grok worker         STOPPED
远程 Grok2API                独立运行，仅 loopback
```

所有验证均为有限命令，不会留下 DeBot4 常驻采集、交易或事件触发 Grok 进程。
