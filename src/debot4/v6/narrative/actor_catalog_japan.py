"""Reviewed Japan-facing ecosystem and narrative accounts."""

from .actor_catalog_types import EXACT_POST_REVIEW, KOL, actor
from .actors import ActorTier as T


JAPAN_ACTORS = (
    actor("missbitcoin_mai", "408665753", "Miss Bitcoin Mai", "Japan-facing protocol founder and event organizer", T.DOMAIN_EXPERT, ("ethereum", "bitcoin"), KOL, languages=("ja", "en"), regions=("japan",), priority=8),
    actor(
        "kenjiquest", "1427824793034784774", "Kenji",
        "Base Japan community co-founder and Japanese RWA/meme community catalyst",
        T.DOMAIN_EXPERT, ("base", "ethereum", "robinhood"), KOL,
        languages=("ja", "en"), regions=("japan",),
        telegram=("base_Japanese",), priority=7, basis=EXACT_POST_REVIEW,
        evidence=("https://x.com/kenjiquest/status/2086703666078081349",),
        risks=("ecosystem community affiliation; not independent market evidence",),
    ),
    actor(
        "saizyo_crypto", "1486425282022379520", "Saizyo",
        "Japanese onchain, TGE, and fast narrative analyst",
        T.DOMAIN_EXPERT, ("ethereum", "solana", "global"), KOL,
        languages=("ja", "en"), regions=("japan",), priority=7,
        basis=EXACT_POST_REVIEW,
        evidence=("https://x.com/saizyo_crypto/status/2086857851650342984",),
        risks=("market analysis is a lead, not independent performance proof",),
    ),
    actor(
        "vanity358", "371981742", "Vanity",
        "Japanese meme community and KOL-team propagation account",
        T.PROPAGATION_KOL, ("solana", "bsc", "global"), KOL,
        languages=("ja", "en"), regions=("japan",), priority=9,
        basis=EXACT_POST_REVIEW,
        evidence=("https://x.com/vanity358/status/2063145774574363058",),
        risks=("community and KOL-team affiliation; high promotion/conflict risk",),
    ),
    actor(
        "golocojp", "1454902124635058179", "Maru2",
        "Japanese Robinhood meme and tokenized-stock liquidity narrative explainer",
        T.PROPAGATION_KOL, ("robinhood", "solana", "ethereum", "rwa"), KOL,
        languages=("ja", "en"), regions=("japan",), priority=6,
        basis=EXACT_POST_REVIEW,
        evidence=("https://x.com/golocojp/status/2079962189860045175",),
        risks=("interpretation is a research lead, not token endorsement proof",),
    ),
    actor(
        "ametomuchi123", "934954582542663683", "飴と鞭",
        "Japanese cross-chain DeBot, wallet-flow, and meme-risk workflow commentator",
        T.PROPAGATION_KOL, ("solana", "bsc", "robinhood"), KOL,
        languages=("ja", "en"), regions=("japan",),
        telegram=("cryptokusacoin",), priority=7, basis=EXACT_POST_REVIEW,
        evidence=("https://x.com/ametomuchi123/status/2086662586461016169",),
        risks=("performance claims are self-reported; Telegram is reference-only",),
    ),
    actor(
        "Solamurai", "1828715424155889664", "Crypto Samurai",
        "Japanese Solana trenches and smart-wallet propagation account",
        T.PROPAGATION_KOL, ("solana",), KOL,
        languages=("ja", "en"), regions=("japan",), priority=10,
        basis=EXACT_POST_REVIEW,
        evidence=("https://x.com/Solamurai/status/1937492989913260479",),
        risks=("trading edge and performance are self-reported with weak profile evidence",),
    ),
    actor(
        "sunapooh67", "2042393918273454080", "suna",
        "Japanese RWA-meme attention-rotation commentator tracking Robinhood and BSC",
        T.PROPAGATION_KOL, ("robinhood", "bsc", "rwa"), KOL,
        languages=("ja",), regions=("japan",), priority=10,
        basis=EXACT_POST_REVIEW,
        evidence=("https://x.com/sunapooh67/status/2084011412578537640",),
        risks=(
            "replacement account with unverified historical influence and performance",
            "position-biased trend commentary; use only as a propagation clue",
        ),
    ),
)
