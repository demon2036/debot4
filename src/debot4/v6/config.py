"""Validated TOML configuration for the clean v6 runtime."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    database: Path
    state_path: Path
    event_log_path: Path
    rank_state_path: Path
    loop_seconds: float
    debot_poll_seconds: float
    ranks_poll_seconds: float
    mark_poll_seconds: float
    dashboard_host: str
    dashboard_port: int
    max_open_buys: int
    bootstrap_pages: int
    history_lookback_seconds: float
    decision_queue_size: int


@dataclass(frozen=True, slots=True)
class ApiConfig:
    chrome_profile: Path
    debot_timeout_seconds: float
    max_response_bytes: int
    rpc_endpoints: tuple[str, ...]
    rpc_timeout_seconds: float
    goplus_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    version: str
    notional_usd: Decimal
    signal_max_age_seconds: float
    min_fdv_usd: Decimal
    max_fdv_usd: Decimal
    min_liquidity_usd: Decimal
    max_buy_tax_pct: Decimal
    max_sell_tax_pct: Decimal
    max_price_impact_bps: Decimal
    max_round_trip_loss_bps: Decimal
    max_block_age_seconds: float
    max_quote_age_seconds: float
    max_head_lag_blocks: int
    max_observation_gap_seconds: float
    require_open_source: bool
    target_multiple: Decimal
    stop_multiple: Decimal


@dataclass(frozen=True, slots=True)
class AppConfig:
    root: Path
    runtime: RuntimeConfig
    api: ApiConfig
    strategy: StrategyConfig


def load_config(path: str | Path, *, root: str | Path | None = None) -> AppConfig:
    config_path = Path(path).expanduser().resolve()
    base = Path(root).expanduser().resolve() if root else config_path.parent.parent
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)
    run = _section(raw, "runtime")
    api = _section(raw, "api")
    strategy = _section(raw, "strategy")
    runtime = RuntimeConfig(
        database=_relative(base, run.get("database", "var/v6/ledger.sqlite3")),
        state_path=_relative(base, run.get("state_path", "var/v6/state.json")),
        event_log_path=_relative(base, run.get("event_log_path", "var/v6/events.jsonl")),
        rank_state_path=_relative(base, run.get("rank_state_path", "var/v6/ranks.json")),
        loop_seconds=_positive(run.get("loop_seconds", 0.25), "loop_seconds"),
        debot_poll_seconds=_positive(run.get("debot_poll_seconds", 1.0), "debot_poll_seconds"),
        ranks_poll_seconds=_positive(
            run.get("ranks_poll_seconds", 0.75), "ranks_poll_seconds"
        ),
        mark_poll_seconds=_positive(run.get("mark_poll_seconds", 0.25), "mark_poll_seconds"),
        dashboard_host=str(run.get("dashboard_host", "0.0.0.0")),
        dashboard_port=_integer(run.get("dashboard_port", 8766), "dashboard_port", 1, 65535),
        max_open_buys=_integer(run.get("max_open_buys", 8), "max_open_buys", 1, 128),
        bootstrap_pages=_integer(run.get("bootstrap_pages", 64), "bootstrap_pages", 1, 256),
        history_lookback_seconds=_positive(
            run.get("history_lookback_seconds", 2_592_000),
            "history_lookback_seconds",
        ),
        decision_queue_size=_integer(
            run.get("decision_queue_size", 256), "decision_queue_size", 8, 4096
        ),
    )
    endpoints = api.get("rpc_endpoints") or [
        "https://bsc-mainnet.public.blastapi.io",
        "https://bsc.publicnode.com",
    ]
    if not isinstance(endpoints, list) or not endpoints:
        raise ValueError("api.rpc_endpoints must be a non-empty list")
    apis = ApiConfig(
        chrome_profile=_relative(
            Path.home(), api.get("chrome_profile", ".config/google-chrome")
        ),
        debot_timeout_seconds=_positive(
            api.get("debot_timeout_seconds", 5.0), "debot_timeout_seconds"
        ),
        max_response_bytes=_integer(
            api.get("max_response_bytes", 4 * 1024 * 1024),
            "max_response_bytes",
            1024,
            8 * 1024 * 1024,
        ),
        rpc_endpoints=tuple(str(item) for item in endpoints),
        rpc_timeout_seconds=_positive(
            api.get("rpc_timeout_seconds", 3.0), "rpc_timeout_seconds"
        ),
        goplus_timeout_seconds=_positive(
            api.get("goplus_timeout_seconds", 4.0), "goplus_timeout_seconds"
        ),
    )
    rules = StrategyConfig(
        version=str(strategy.get("version", "v6-debot-kol-narrative-block")),
        notional_usd=_decimal(strategy.get("notional_usd", "10"), "notional_usd"),
        signal_max_age_seconds=_positive(
            strategy.get("signal_max_age_seconds", 20), "signal_max_age_seconds"
        ),
        min_fdv_usd=_decimal(strategy.get("min_fdv_usd", "20000"), "min_fdv_usd"),
        max_fdv_usd=_decimal(strategy.get("max_fdv_usd", "3000000"), "max_fdv_usd"),
        min_liquidity_usd=_decimal(
            strategy.get("min_liquidity_usd", "5000"), "min_liquidity_usd"
        ),
        max_buy_tax_pct=_decimal(
            strategy.get("max_buy_tax_pct", "10"), "max_buy_tax_pct"
        ),
        max_sell_tax_pct=_decimal(
            strategy.get("max_sell_tax_pct", "10"), "max_sell_tax_pct"
        ),
        max_price_impact_bps=_decimal(
            strategy.get("max_price_impact_bps", "500"), "max_price_impact_bps"
        ),
        max_round_trip_loss_bps=_decimal(
            strategy.get("max_round_trip_loss_bps", "2500"),
            "max_round_trip_loss_bps",
        ),
        max_block_age_seconds=_positive(
            strategy.get("max_block_age_seconds", 4), "max_block_age_seconds"
        ),
        max_quote_age_seconds=_positive(
            strategy.get("max_quote_age_seconds", 1.5), "max_quote_age_seconds"
        ),
        max_head_lag_blocks=_integer(
            strategy.get("max_head_lag_blocks", 0),
            "max_head_lag_blocks", 0, 3,
        ),
        max_observation_gap_seconds=_positive(
            strategy.get("max_observation_gap_seconds", 5),
            "max_observation_gap_seconds",
        ),
        require_open_source=bool(strategy.get("require_open_source", True)),
        target_multiple=_decimal(
            strategy.get("target_multiple", "1.5"), "target_multiple"
        ),
        stop_multiple=_decimal(
            strategy.get("stop_multiple", "0.75"), "stop_multiple"
        ),
    )
    if rules.min_fdv_usd >= rules.max_fdv_usd:
        raise ValueError("min_fdv_usd must be below max_fdv_usd")
    if rules.stop_multiple <= 0 or rules.stop_multiple >= 1:
        raise ValueError("stop_multiple must be within (0, 1)")
    if rules.target_multiple <= 1:
        raise ValueError("target_multiple must exceed 1")
    return AppConfig(base, runtime, apis, rules)


def _section(raw: dict[str, object], name: str) -> dict[str, object]:
    value = raw.get(name) or {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a TOML table")
    return value


def _relative(base: Path, value: object) -> Path:
    path = Path(str(value)).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _positive(value: object, name: str) -> float:
    result = float(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _integer(value: object, name: str, low: int, high: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    result = int(value)
    if not low <= result <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return result


def _decimal(value: object, name: str) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError(f"{name} must be a non-negative finite decimal")
    return result
