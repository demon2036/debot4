"""Evidence-first historical golden-dog research boundaries."""

from .models import Candle, EvidenceReceipt, MarketTrace, Observation, TokenSeed
from .market_waves import (
    MarketWave,
    MarketWaveReplay,
    WavePhaseBounds,
    replay_market_waves,
    wave_phase_bounds,
)
from .kol_evidence import KOL_WALLET_ATTRIBUTIONS, WalletAttribution
from .qualification import GoldenDogAssessment, Verdict, qualify_golden_dog
from .rules import GOLD_MIN_PEAK_FDV_USD, analyze_market

__all__ = [
    "Candle",
    "EvidenceReceipt",
    "GOLD_MIN_PEAK_FDV_USD",
    "GoldenDogAssessment",
    "KOL_WALLET_ATTRIBUTIONS",
    "MarketTrace",
    "MarketWave",
    "MarketWaveReplay",
    "Observation",
    "TokenSeed",
    "Verdict",
    "WalletAttribution",
    "WavePhaseBounds",
    "analyze_market",
    "qualify_golden_dog",
    "replay_market_waves",
    "wave_phase_bounds",
]
