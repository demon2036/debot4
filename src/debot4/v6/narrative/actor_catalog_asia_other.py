"""Reviewed Asia-facing accounts not assigned to one country catalog."""

from .actor_catalog_types import EXACT_POST_REVIEW, KOL, actor
from .actors import ActorTier as T


OTHER_ASIA_ACTORS = (
    actor(
        "stitchdegen", "1863528077701046272", "Stitch",
        "Robinhood-native launchpad and meme market-share thesis commentator",
        T.PROPAGATION_KOL, ("robinhood", "bsc", "solana"), KOL,
        regions=("asia", "global"), telegram=("Yostitch2",), priority=6,
        basis=EXACT_POST_REVIEW,
        evidence=("https://x.com/stitchdegen/status/2086912035904999818",),
        risks=("token-specific thesis and disclosed position can bias conclusions",),
    ),
    actor(
        "Medo2885", "1424832192589541384", "Medo",
        "Ape, Base, and Ethereum community propagation account",
        T.PROPAGATION_KOL, ("base", "ethereum"), KOL,
        regions=("asia", "global"), telegram_public=("MSNFT0",), priority=10,
        risks=("promotion-heavy X feed; Telegram messages are raw leads only",),
    ),
    actor(
        "bull_bnb", "1297503202464718850", "Bull BNB",
        "BNB and social-trading attention-loop narrative commentator",
        T.PROPAGATION_KOL, ("bsc", "bnb", "social-trading", "global"), KOL,
        regions=("asia", "global"), priority=6, basis=EXACT_POST_REVIEW,
        evidence=("https://x.com/bull_bnb/status/2086657767017001386",),
        risks=("narrative thesis is not token endorsement or performance evidence",),
    ),
)
