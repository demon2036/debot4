"""Pure three-gate qualification for evidence-backed golden dogs."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import re

from .models import Observation, normalize_evm_address


_TX_HASH = re.compile(r"0x[0-9a-f]{64}")
_PROVIDERS = {"debot", "gmgn"}


class Verdict(str, Enum):
    PASS = "PASS"
    WAIT = "WAIT"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class KolWalletTrade:
    provider_alias: str
    bought_at: int
    volume_usd: Decimal
    token_amount: Decimal
    wallet: str | None = None
    transaction_hash: str | None = None
    swap_verified: bool | None = None
    risk_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.provider_alias.strip() or self.bought_at <= 0:
            raise ValueError("KOL trade needs an alias and buy time")
        if self.volume_usd <= 0 or self.token_amount <= 0:
            raise ValueError("KOL trade amounts must be positive")
        wallet = normalize_evm_address(self.wallet) if self.wallet else None
        tx_hash = self.transaction_hash.casefold() if self.transaction_hash else None
        if tx_hash and not _TX_HASH.fullmatch(tx_hash):
            raise ValueError("KOL trade transaction hash is invalid")
        if self.swap_verified is not None and not (wallet and tx_hash):
            raise ValueError("swap verdict needs an exact wallet and transaction")
        object.__setattr__(self, "provider_alias", self.provider_alias.strip())
        object.__setattr__(self, "wallet", wallet)
        object.__setattr__(self, "transaction_hash", tx_hash)
        object.__setattr__(
            self, "risk_tags",
            tuple(sorted({item.strip().casefold() for item in self.risk_tags if item.strip()})),
        )


@dataclass(frozen=True, slots=True)
class ProviderKolBuy:
    provider: str
    chain: str
    token_address: str
    signal_id: str
    provider_event_at: int
    provider_url: str
    trades: tuple[KolWalletTrade, ...]

    def __post_init__(self) -> None:
        provider = self.provider.strip().casefold()
        if provider not in _PROVIDERS:
            raise ValueError("KOL-buy provider must be DeBot or GMGN")
        if not self.signal_id.strip() or self.provider_event_at <= 0:
            raise ValueError("provider KOL-buy record is incomplete")
        if not self.provider_url.startswith("https://") or not self.trades:
            raise ValueError("provider KOL-buy evidence needs a URL and trades")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "chain", self.chain.strip().casefold())
        object.__setattr__(self, "token_address", normalize_evm_address(self.token_address))
        object.__setattr__(self, "signal_id", self.signal_id.strip())
        object.__setattr__(self, "trades", tuple(self.trades))


@dataclass(frozen=True, slots=True)
class ManipulationEvidence:
    checked_at: int
    genuine_kol_swap: bool | None
    shared_funding: bool | None
    concentrated_supply: bool | None
    wash_or_circular_trading: bool | None
    evidence_urls: tuple[str, ...]
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.checked_at <= 0 or not self.evidence_urls:
            raise ValueError("manipulation screen needs timestamped evidence")
        if any(not item.startswith("https://") for item in self.evidence_urls):
            raise ValueError("manipulation evidence URLs must use HTTPS")
        object.__setattr__(self, "evidence_urls", tuple(dict.fromkeys(self.evidence_urls)))
        object.__setattr__(self, "notes", tuple(self.notes))


@dataclass(frozen=True, slots=True)
class GateAssessment:
    verdict: Verdict
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GoldenDogAssessment:
    verdict: Verdict
    market: GateAssessment
    kol_buy: GateAssessment
    causal_timing: GateAssessment
    manipulation: GateAssessment


def qualify_golden_dog(
    observation: Observation,
    provider_buys: tuple[ProviderKolBuy, ...] = (),
    manipulation: ManipulationEvidence | None = None,
    *,
    kol_coverage_complete: bool = False,
) -> GoldenDogAssessment:
    market = _market_gate(observation)
    kol_buy = _kol_gate(observation, provider_buys, kol_coverage_complete)
    causal_timing = _causal_timing_gate(observation, provider_buys)
    screen = _manipulation_gate(manipulation)
    gates = (market, kol_buy, screen)
    if any(item.verdict is Verdict.REJECT for item in gates):
        verdict = Verdict.REJECT
    elif all(item.verdict is Verdict.PASS for item in gates):
        verdict = Verdict.PASS
    else:
        verdict = Verdict.WAIT
    return GoldenDogAssessment(verdict, market, kol_buy, causal_timing, screen)


def _market_gate(observation: Observation) -> GateAssessment:
    if observation.status != "complete":
        return GateAssessment(Verdict.WAIT, ("market_history_incomplete",))
    if observation.meets_peak_threshold:
        return GateAssessment(Verdict.PASS, ("peak_mc_or_fdv_at_least_500k",))
    return GateAssessment(Verdict.REJECT, ("peak_mc_or_fdv_below_500k",))


def _kol_gate(
    observation: Observation,
    evidence: tuple[ProviderKolBuy, ...],
    coverage_complete: bool,
) -> GateAssessment:
    matches = tuple(
        item for item in evidence
        if item.chain == observation.chain and item.token_address == observation.address
    )
    if matches:
        trades = tuple(trade for item in matches for trade in item.trades)
        clean = tuple(
            trade for trade in trades
            if trade.swap_verified is True
            and not _manipulative_trade(trade)
            and observation.window_start <= trade.bought_at < observation.window_end_exclusive
        )
        if clean:
            providers = ",".join(sorted({item.provider for item in matches}))
            return GateAssessment(Verdict.PASS, (f"verified_provider_kol_buy:{providers}",))
        if any(_manipulative_trade(trade) for trade in trades):
            return GateAssessment(Verdict.REJECT, ("kol_buy_is_wash_trader_tagged",))
        if any(trade.swap_verified is False for trade in trades):
            return GateAssessment(Verdict.REJECT, ("provider_event_is_not_verified_swap",))
        if any(trade.swap_verified is None for trade in trades):
            return GateAssessment(Verdict.WAIT, ("provider_kol_buy_needs_chain_verification",))
        if not any(
            observation.window_start <= trade.bought_at < observation.window_end_exclusive
            for trade in trades
        ):
            return GateAssessment(Verdict.REJECT, ("provider_kol_buy_outside_market_window",))
        return GateAssessment(Verdict.REJECT, ("no_verified_clean_provider_kol_buy",))
    if observation.max_kols > 0:
        return GateAssessment(Verdict.WAIT, ("aggregate_kol_count_is_not_buy_evidence",))
    if coverage_complete:
        return GateAssessment(Verdict.REJECT, ("no_debot_or_gmgn_kol_buy",))
    return GateAssessment(Verdict.WAIT, ("kol_buy_search_incomplete",))


def _causal_timing_gate(
    observation: Observation,
    evidence: tuple[ProviderKolBuy, ...],
) -> GateAssessment:
    trades = tuple(
        trade
        for item in evidence
        if item.chain == observation.chain and item.token_address == observation.address
        for trade in item.trades
        if trade.swap_verified is True
        and not _manipulative_trade(trade)
        and observation.window_start <= trade.bought_at < observation.window_end_exclusive
    )
    if not trades:
        return GateAssessment(Verdict.WAIT, ("causal_timing_unavailable",))
    if observation.peak_at is None:
        return GateAssessment(Verdict.WAIT, ("market_peak_time_missing",))
    if any(trade.bought_at < observation.peak_at for trade in trades):
        return GateAssessment(Verdict.PASS, ("verified_kol_buy_precedes_peak",))
    return GateAssessment(Verdict.REJECT, ("provider_kol_buy_is_post_peak_only",))


def _manipulative_trade(trade: KolWalletTrade) -> bool:
    return bool({"wash_trader", "sandwich_bot", "sybil"} & set(trade.risk_tags))


def _manipulation_gate(evidence: ManipulationEvidence | None) -> GateAssessment:
    if evidence is None:
        return GateAssessment(Verdict.WAIT, ("manipulation_screen_missing",))
    unsafe = []
    if evidence.genuine_kol_swap is False:
        unsafe.append("kol_event_is_not_a_genuine_swap")
    if evidence.shared_funding is True:
        unsafe.append("deployer_kol_or_wallets_share_funding")
    if evidence.concentrated_supply is True:
        unsafe.append("supply_is_concentrated")
    if evidence.wash_or_circular_trading is True:
        unsafe.append("wash_or_circular_trading_detected")
    if unsafe:
        return GateAssessment(Verdict.REJECT, tuple(unsafe))
    values = (
        evidence.genuine_kol_swap,
        evidence.shared_funding,
        evidence.concentrated_supply,
        evidence.wash_or_circular_trading,
    )
    if any(value is None for value in values):
        return GateAssessment(Verdict.WAIT, ("manipulation_checks_incomplete",))
    return GateAssessment(Verdict.PASS, ("no_manipulation_indicators_found",))
