# 北斗因果回放候选（公开数据）

- 样本：27；有完整 1 小时公开 OHLC：24；FxTwitter 时间戳核验：27。
- 纳入：帖子必须明确主 CA，且属于上涨前或上涨途中的判断；候选池必须早于帖子创建。
- 排除：所有 `retrospective`、低价/峰值/倍数复盘、只讲方法无明确 CA、主 CA 歧义或发帖前池无法验证的帖子。
- 入口代理：发帖后的下一完整 UTC 分钟起，取首根实际出现的 1m K 线 open；一小时 OHLC 聚合到该窗口结束。
- 收益代理：`high/open-1`、`close/open-1`、`low/open-1`；不是实盘收益，不含滑点、税、gas、MEV，也没有假设能以最高价退出。
- 近似 FDV：历史 USD 价格 × DexPaprika 当前报告总供应量；供应变化会造成误差。历史流动性无法重建，JSONL 中保持 `null`。
- 来源：FxTwitter（公开发布时间）、DexScreener（CA→池和建池时间）、DexPaprika/GeckoTerminal（池元数据、1m OHLC）。每案保留完整端点和不确定性。

## 缺失项

  - row 29 北极熊USD1大赛选标：pre-post pool identified, but public 1m OHLC unavailable
  - row 34 SPACE加密版Starlink：pre-post pool identified, but public 1m OHLC unavailable
  - row 48 BORT BAP-578协议叙事：pre-post pool identified, but public 1m OHLC unavailable
