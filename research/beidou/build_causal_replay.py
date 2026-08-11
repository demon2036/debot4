#!/usr/bin/env python3
"""Build causally valid Beidou tweet-to-DEX one-hour replays."""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "narrative_corpus_69.jsonl"
OUT = ROOT / "causal_replay_candidates.jsonl"
REPORT = ROOT / "causal_replay_report.md"
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

# Only posts that state a primary CA and make a contemporaneous/forward judgment.
CASES = {
    8: ("8J69rbLTzWWgUJziFY8jeu5tDwEPBwUz4pKBMr5rpump", "in_progress", "正文仍建议当时布局头仓；不采用归档中的后续63M或5.1M价格。"),
    16: ("H2yHLoC24dM5v1Vjh2Poqx7fZ9mp8EfR2MYseXScpump", "forward", "正文定义为初筛和底部埋伏，NASDAQ合并被写成未来催化。"),
    22: ("FyPDfX92B4uEk4zZouy96d1Kk1LgnCznBpzAFSsZpump", "forward", "正文给出当时1.5M附近策略位，并列出尚待上线功能。"),
    25: ("TVKv96p5SD93veeWTZzppv17r867ij6tmnDpUhZpump", "forward", "正文为初筛，围绕出狱后新发射项目作当时判断。"),
    28: ("G63pAYWkZd71Jdy83bbdvs6HMQxaYVWy5jsS1hK3pump", "forward", "正文评估正在实时构建的工具及后续传播可能。"),
    29: ("0x9f9ac02452e635f80ea071cb223673a6d5ce4444", "in_progress", "正文给出USD1大赛实时榜单中的当时选标逻辑。"),
    31: ("7iX4yQ4zTraFSRXEGpF89emA9xGrhgv6jX57dMENpump", "in_progress", "正文称K线仍在三角收敛并酝酿下一波。"),
    32: ("8Jx8AAHj86wbQgUTjGuj6GTTL5Ps3cqxKRTvpaJApump", "in_progress", "正文给出3至4M回调建议并明确DEV风险。"),
    34: ("0x87acfa3fd7a6e0d48677d070644d76905c2bdc00", "in_progress", "正文按当时产品、合作与交易所进展评分，未引用后续价格。"),
    35: ("EwEJ5R1im54MowvsGwYUkyfWRMV1qcRL21PumVd4pump", "in_progress", "正文称启动也近了并据当前三角结构评级。"),
    38: ("61Wj56QgGyyB966T7YsMzEAKRLcMvJpDbPzjkrCZc4Bi", "in_progress", "正文分析当前持仓结构和大户组局，未使用后续结果。"),
    41: ("0xb695559b26bb2c9703ef1935c37aeae9526bab07", "forward", "采用MOLT首篇研判；排除41分钟后的跟进帖，正文描述未来产品催化。"),
    45: ("2akXpuyFXAVN5YofZpZMfBp2Vxognpmv9NooBMuHpump", "in_progress", "多CA帖子只取正文标注为PRIMARY的首个CA，并按当时结构判断。"),
    46: ("0x587cd533f418825521f3a1daa7ccd1e7339a1b07", "forward", "正文评估尚在建设中的代理支付设施与未来交付。"),
    47: ("9S8edqWxoWz5LYLnxWUmWBJnePg35WfdYQp7HQkUpump", "in_progress", "正文按当时文化冲突、传播与风险作判断。"),
    48: ("0x2a846aaaf896ef393ccb76398c1d96ea97374444", "in_progress", "正文围绕当时BAP-578协议与生态位置研判。"),
    50: ("21CnrFRqvEVkQZUTFmTXjcsJTLZhRY51ohoaCPwRpump", "forward", "正文明确原作者尚未公开认领，把认领写成未来催化。"),
    51: ("9pTTktFyx6gK9Hxqh4CN7ER2Pcn8ahwtWz6FXY6mpump", "forward", "正文在400K附近给出未来宝可梦周年日催化。"),
    53: ("2qT8JVotQ2C1gKbqpuqNatkpSBWxiKHbXkCyTqH9pump", "in_progress", "正文在约1M时提出生态对抗叙事，未引用后续结果。"),
    54: ("AWpD39myXc7emw5M9cMCofkbo92x5FKWdGHWYpZFdoge", "in_progress", "正文基于刚发生的敲钟事件判断叙事仍可持续。"),
    55: ("25E8X8fPnT9AdU1nA78snybnzVxkDvv5rK663Ngrpump", "forward", "正文评估初步产品框架，并将白皮书和审计列为待验证项。"),
    58: ("Hh3oTaqDCKKfdBgsQEvxp9sUwyNf8x9qmKqEMLBWpump", "in_progress", "正文给出1.5至2M策略位；不采用归档中的后续4M自报。"),
    61: ("5QhQE7yRMgYHzs7Vq3y2Wnc2SAkMwLYrQc4RHNipump", "forward", "正文明确爆发点与风险都在未来正式认领。"),
    63: ("9MS4ptpnnJhBsWYShPw1tP1ykAmwEmkPXP9aLVpwpump", "in_progress", "正文给出头仓加500K跌补的当时策略。"),
    66: ("0xc20e45e49e0e79f0fc81e71f05fd2772d6587777", "forward", "正文建议等待获利盘回落到1M；不采用次日三倍复盘。"),
    68: ("0xe97b7ba92e5058d0456894ff6f969683cfd44444", "forward", "正文把Binance Skills Hub正式公布写成未来爆发催化。"),
    69: ("BprouMoau36y1x6TxiLbHd59Q2eJgrKSBGdzcc6pump", "in_progress", "正文在约240K时补充仍在发展的事件链，不采用未来价格。"),
}


def get_json(url: str, retries: int = 3):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as response:
                return json.load(response), None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            error = f"{type(exc).__name__}: {exc}"
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    return None, error


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def replay_url(chain: str, pair: str, start: datetime, end: datetime) -> str:
    query = urllib.parse.urlencode({"start": iso(start), "end": iso(end), "interval": "1m", "limit": 100})
    return f"https://api.dexpaprika.com/networks/{chain}/pools/{pair}/ohlcv?{query}"


def gecko_url(chain: str, pair: str, end: datetime) -> str:
    query = urllib.parse.urlencode({"aggregate": 1, "before_timestamp": int(end.timestamp()), "limit": 100, "currency": "usd", "token": "base"})
    return f"https://api.geckoterminal.com/api/v2/networks/{chain}/pools/{pair}/ohlcv/minute?{query}"


def build_case(row: int, source: dict) -> dict:
    ca, timing_class, evidence = CASES[row]
    corpus_at = datetime.fromisoformat(source["utc"].replace("Z", "+00:00"))
    fx_url = f"https://api.fxtwitter.com/status/{source['tweet_id']}"
    fx, fx_error = get_json(fx_url)
    fx_ts = (fx or {}).get("tweet", {}).get("created_timestamp")
    published = datetime.fromtimestamp(fx_ts, timezone.utc) if fx_ts else corpus_at
    target = published.replace(second=0, microsecond=0) + timedelta(minutes=1)
    end = target + timedelta(hours=1)
    ds_url = f"https://api.dexscreener.com/latest/dex/tokens/{ca}"
    ds, ds_error = get_json(ds_url)
    pairs = []
    for pair in (ds or {}).get("pairs") or []:
        created_ms = pair.get("pairCreatedAt")
        base = (pair.get("baseToken") or {}).get("address", "")
        if created_ms and base.lower() == ca.lower() and created_ms <= int(published.timestamp() * 1000):
            pairs.append(pair)
    selected = bars = pool_meta = ohlcv_url = ohlcv_provider = None
    ohlcv_errors = []
    for pair in pairs:
        url = replay_url(pair["chainId"], pair["pairAddress"], target, end)
        data, error = get_json(url)
        if isinstance(data, list) and data:
            selected, bars, ohlcv_url, ohlcv_provider = pair, data, url, "DexPaprika"
            meta_url = f"https://api.dexpaprika.com/networks/{pair['chainId']}/pools/{pair['pairAddress']}"
            pool_meta, _ = get_json(meta_url)
            break
        fallback = gecko_url(pair["chainId"], pair["pairAddress"], end)
        gecko, gecko_error = get_json(fallback, retries=3)
        raw_bars = (gecko or {}).get("data", {}).get("attributes", {}).get("ohlcv_list", [])
        raw_bars = [bar for bar in raw_bars if int(target.timestamp()) <= bar[0] < int(end.timestamp())]
        if raw_bars:
            bars = [{"time_open": iso(datetime.fromtimestamp(bar[0], timezone.utc)), "open": bar[1], "high": bar[2], "low": bar[3], "close": bar[4], "volume": bar[5]} for bar in raw_bars]
            selected, ohlcv_url, ohlcv_provider = pair, fallback, "GeckoTerminal"
            meta_url = f"https://api.dexpaprika.com/networks/{pair['chainId']}/pools/{pair['pairAddress']}"
            pool_meta, _ = get_json(meta_url)
            break
        ohlcv_errors.append({"pair": pair.get("pairAddress"), "dexpaprika_url": url, "dexpaprika": error or "empty_ohlcv", "geckoterminal_url": fallback, "geckoterminal": gecko_error or "empty_ohlcv"})
    timestamp_delta = abs((published - corpus_at).total_seconds())
    result = {
        "case_id": f"beidou-{row:02d}-{source['tweet_id']}", "corpus_row": row,
        "case_name": source["case_name"], "tweet_id": source["tweet_id"], "published_at": iso(published),
        "timestamp_verification": {"status": "verified" if fx_ts and timestamp_delta <= 1 else "corpus_fallback", "corpus_at": source["utc"], "fxtwitter_created_timestamp": fx_ts, "delta_seconds": timestamp_delta if fx_ts else None, "error": fx_error},
        "timing_class": timing_class, "timing_evidence": evidence,
        "token": {"ca": ca, "chain": selected.get("chainId") if selected else None, "symbol": (selected or {}).get("baseToken", {}).get("symbol"), "ca_resolution": "explicit_primary_ca_in_post"},
        "pool": None, "replay": None,
        "sources": {"post": source["source_url"], "post_mirror": fx_url, "pair_discovery": ds_url, "pool_metadata": None, "ohlcv": ohlcv_url, "ohlcv_provider": ohlcv_provider},
        "uncertainties": ["1分钟K线不是可成交报价；未计滑点、税、gas、MEV。", "历史流动性深度不可由本数据重建，因此只能证明池存在且窗口内有成交。"],
    }
    if not selected:
        if pairs:
            candidate = pairs[0]
            created = datetime.fromtimestamp(candidate["pairCreatedAt"] / 1000, timezone.utc)
            result["token"].update({"chain": candidate.get("chainId"), "symbol": candidate.get("baseToken", {}).get("symbol")})
            result["pool"] = {"address": candidate["pairAddress"], "dex": candidate.get("dexId"), "created_at": iso(created), "existed_at_post": created <= published, "quote_symbol": candidate.get("quoteToken", {}).get("symbol"), "selection_rule": "first current DexScreener-ranked pre-post base-token pool; activity at post unverified", "historical_liquidity_usd": None}
            reason = "pre-post pool identified, but public 1m OHLC unavailable"
        else:
            reason = "no pre-post base-token pool found in current DexScreener discovery"
        result["replay"] = {"status": "missing", "reason": reason, "attempts": ohlcv_errors, "dexscreener_error": ds_error}
        return result
    created = datetime.fromtimestamp(selected["pairCreatedAt"] / 1000, timezone.utc)
    result["pool"] = {"address": selected["pairAddress"], "dex": selected.get("dexId"), "created_at": iso(created), "existed_at_post": created <= published, "quote_symbol": selected.get("quoteToken", {}).get("symbol"), "selection_rule": "first current DexScreener-ranked pre-post base-token pool with non-empty window OHLC", "historical_liquidity_usd": None}
    meta_url = f"https://api.dexpaprika.com/networks/{selected['chainId']}/pools/{selected['pairAddress']}"
    result["sources"]["pool_metadata"] = meta_url
    bars = sorted(bars, key=lambda bar: bar["time_open"])
    first, last = bars[0], bars[-1]
    entry = first["open"]
    high, low = max(bar["high"] for bar in bars), min(bar["low"] for bar in bars)
    volume = sum(float(bar.get("volume") or 0) for bar in bars)
    supply = None
    for token in (pool_meta or {}).get("tokens") or []:
        if token.get("id", "").lower() == ca.lower() and token.get("total_supply") is not None:
            supply = float(token["total_supply"]) / (10 ** int(token.get("decimals") or 0))
    fdv = ({name: price * supply for name, price in {"entry": entry, "high": high, "low": low, "close": last["close"]}.items()} if supply else None)
    result["replay"] = {"status": "complete", "entry_rule": "first observed 1m bar at/after the next full UTC minute", "target_at": iso(target), "window_end": iso(end), "first_bar_at": first["time_open"], "entry_lag_seconds": datetime.fromisoformat(first["time_open"].replace("Z", "+00:00")).timestamp() - target.timestamp(), "bar_count": len(bars), "ohlc_usd": {"open": entry, "high": high, "low": low, "close": last["close"]}, "reported_volume_usd": volume, "peak_return_pct": (high / entry - 1) * 100, "close_return_pct": (last["close"] / entry - 1) * 100, "max_drawdown_from_entry_pct": (low / entry - 1) * 100, "approx_fdv_usd": fdv, "supply_proxy": supply, "fdv_method": "historical USD price multiplied by current DexPaprika-reported total supply"}
    result["uncertainties"].append("近似FDV假设当前报告的总供应量在发帖窗口已成立；可增发、销毁或重定基会使估算失真。")
    return result


def main() -> None:
    rows = {i: json.loads(line) for i, line in enumerate(CORPUS.read_text().splitlines(), 1)}
    records = []
    for row in CASES:
        print(f"fetching row {row}", flush=True)
        records.append(build_case(row, rows[row]))
        time.sleep(0.15)
    OUT.write_text("".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in records))
    complete = sum(record["replay"]["status"] == "complete" for record in records)
    verified = sum(record["timestamp_verification"]["status"] == "verified" for record in records)
    missing = [f"  - row {record['corpus_row']} {record['case_name']}：{record['replay']['reason']}" for record in records if record["replay"]["status"] != "complete"]
    missing_text = "\n".join(missing) if missing else "  - 无"
    REPORT.write_text(f"""# 北斗因果回放候选（公开数据）\n\n- 样本：{len(records)}；有完整 1 小时公开 OHLC：{complete}；FxTwitter 时间戳核验：{verified}。\n- 纳入：帖子必须明确主 CA，且属于上涨前或上涨途中的判断；候选池必须早于帖子创建。\n- 排除：所有 `retrospective`、低价/峰值/倍数复盘、只讲方法无明确 CA、主 CA 歧义或发帖前池无法验证的帖子。\n- 入口代理：发帖后的下一完整 UTC 分钟起，取首根实际出现的 1m K 线 open；一小时 OHLC 聚合到该窗口结束。\n- 收益代理：`high/open-1`、`close/open-1`、`low/open-1`；不是实盘收益，不含滑点、税、gas、MEV，也没有假设能以最高价退出。\n- 近似 FDV：历史 USD 价格 × DexPaprika 当前报告总供应量；供应变化会造成误差。历史流动性无法重建，JSONL 中保持 `null`。\n- 来源：FxTwitter（公开发布时间）、DexScreener（CA→池和建池时间）、DexPaprika/GeckoTerminal（池元数据、1m OHLC）。每案保留完整端点和不确定性。\n\n## 缺失项\n\n{missing_text}\n""")
    print(json.dumps({"records": len(records), "complete": complete, "timestamp_verified": verified}))


if __name__ == "__main__":
    main()
