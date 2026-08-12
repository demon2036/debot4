"""Deterministic Grok lead-search tasks for Chinese BSC KOL research."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib

from .kol_identity import CHINESE_MEME_KOL_CANDIDATES, LOOKONCHAIN_BSC_TRADERS


@dataclass(frozen=True, slots=True)
class KolSearchTask:
    key: str
    lane: str
    prompt: str

    def __post_init__(self) -> None:
        if not self.key.strip() or self.lane not in {"x", "discovery"}:
            raise ValueError("invalid KOL search task")
        if not self.prompt.strip():
            raise ValueError("KOL search prompt is required")

    @property
    def prompt_sha256(self) -> str:
        return hashlib.sha256(self.prompt.encode("utf-8")).hexdigest()


def chinese_kol_search_tasks(start: date, end_exclusive: date) -> tuple[KolSearchTask, ...]:
    """Build broad omission sweeps plus one authored-post sweep per known handle."""

    if start >= end_exclusive:
        raise ValueError("KOL research dates are invalid")
    bounds = f"UTC [{start.isoformat()}, {end_exclusive.isoformat()})"
    broad = (
        ("omitted-identities", "x", _omitted_prompt(bounds)),
        ("aliases", "x", _alias_prompt(bounds)),
        ("community-lists", "x", _list_prompt(bounds)),
        ("verified-directory-snowball", "x", _directory_snowball_prompt(bounds)),
        ("nickname-history-snowball", "x", _nickname_snowball_prompt(bounds)),
        ("exact-ca-calls", "x", _call_prompt(bounds)),
        ("influence-catalysts", "x", _influence_prompt(bounds)),
        ("provider-labels", "discovery", _provider_prompt(bounds)),
        ("wallet-attribution", "discovery", _wallet_prompt(bounds)),
        ("shadow-account-attribution", "discovery", _shadow_prompt(bounds)),
        ("manipulation-disconfirmation", "discovery", _risk_prompt(bounds)),
    )
    tasks = [KolSearchTask(key, lane, prompt) for key, lane, prompt in broad]
    identities = LOOKONCHAIN_BSC_TRADERS + CHINESE_MEME_KOL_CANDIDATES
    tasks.extend(
        KolSearchTask(
            f"handle:{item.handle.casefold()}",
            "x",
            _handle_prompt(bounds, item.handle, item.display_name, item.aliases),
        )
        for item in identities
    )
    return tuple(tasks)


def _common(bounds: str) -> str:
    return f"""
Research Chinese-language BSC/BNB meme KOL activity in {bounds}. Return direct X status
URLs, exact handles and exact 0x token contracts whenever present. A profile may be a
useful KOL identity even when no wallet is public. Never infer or invent a wallet from
a token contract, ticker, display name, transfer, or follower list. Separate identity,
authored call, provider KOL-buy label, wallet attribution, on-chain buy, and price timing.
This is lead discovery only; explicitly use null for unknown and say when evidence is
only a third-party claim.
""".strip()


def _omitted_prompt(bounds: str) -> str:
    return _common(bounds) + """
\nFind Chinese meme traders or callers omitted from common lists. Search Chinese aliases,
nickname variants, screenshots and replies. Prefer people whose own post discussed a
BSC meme before a visible move. Exclude generic chain/platform accounts unless their
specific post was itself the catalyst. Return every plausible handle with direct URLs.
"""


def _alias_prompt(bounds: str) -> str:
    return _common(bounds) + """
\nMap Chinese nicknames to canonical X handles, including 深大高财生, 深大高材生, 深大,
冷静, 王小二, 大D, 侥幸哥, 慈善家, 猫姐 and name changes. Give the direct profile and
status that demonstrates each mapping; do not treat similar display names as identical.
"""


def _list_prompt(bounds: str) -> str:
    return _common(bounds) + """
\nLocate Chinese community posts that list, rank, recommend, or discuss on-chain meme KOLs.
Return the original list post URLs and all handles literally named. Explain whether each
list is a ranking, fan nomination, performance claim, or merely an unordered directory.
"""


def _directory_snowball_prompt(bounds: str) -> str:
    return f"""Search public X posts in {bounds}. Start from this Chinese community directory:
https://x.com/facai988/status/1982437570467504565 . Inspect its literal handles,
replies, quotes and later related list posts. Find additional Chinese meme callers not
literally present in that directory and return the original status proving each addition.
For every result return only the direct x.com profile/status URLs and quote the source.
Do not infer wallets or a token contract, and do not promote a fan nomination into a
verified KOL. It is acceptable to return no result.
"""


def _nickname_snowball_prompt(bounds: str) -> str:
    return _common(bounds) + """
\nTrace nickname and handle history around 深大高财生/深大高材生/深大 and the Chinese
meme accounts named in https://x.com/facai988/status/1982437570467504565. Search direct
posts that preserve an old handle, new handle, display name or mutual attribution. Return
stable identity evidence and all plausible alternatives; never merge people by nickname.
"""


def _call_prompt(bounds: str) -> str:
    return _common(bounds) + """
\nFind authored Chinese KOL posts containing an exact BSC meme CA before or during a pump.
Prioritize direct status URLs and preserve post time, wording, claimed MC, and whether the
post is a buy call, research, news, tutorial, or post-pump recap. Include competing CAs.
"""


def _influence_prompt(bounds: str) -> str:
    return _common(bounds) + """
\nFind exact posts by CZ, 何一/Yi He, Elon Musk or comparable people that visibly triggered
a BSC meme narrative. Return their original post plus the earliest token-CA attribution
posts, while making clear that the public figure may never have bought or endorsed a CA.
"""


def _provider_prompt(bounds: str) -> str:
    return _common(bounds) + """
\nFind public GMGN or DeBot pages/screenshots that label Chinese handles or wallets as KOL
and show a BSC token buy. Require the exact wallet, CA, buy time and transaction hash when
visible. A max_kols count or generic smart-money tag is not a KOL-buy record.
"""


def _wallet_prompt(bounds: str) -> str:
    return _common(bounds) + """
\nFind independent public wallet-attribution sources for Chinese BSC meme KOLs: self-posts,
signed messages, Lookonchain, Arkham labels, GMGN bound-X profiles, or exact balance/tx
claims. Return source URL, full wallet, claimed owner and attribution strength separately.
"""


def _shadow_prompt(bounds: str) -> str:
    return f"""Search the public web and X in {bounds} for published attribution of
secondary X accounts or secondary BSC
wallets to major Chinese meme KOLs, especially the handles literally listed in
https://x.com/facai988/status/1982437570467504565. A secondary wallet may buy days before
an authored post. Return direct URLs and exact quoted claims only. Accept self-disclosure,
signed proof, provider-bound X profiles, or named investigations. Do not infer ownership
from timing or similar names. It is acceptable to return no result.
Never substitute a token contract for a wallet address.
"""


def _risk_prompt(bounds: str) -> str:
    return _common(bounds) + """
\nSearch for evidence that apparent Chinese KOL buys were transfers, paid promotion,
post-pump buys, shared-funded wallets, wash/circular trades, concentrated holders, or
bundled launches. Return direct contrary evidence; do not call a token clean by default.
"""


def _handle_prompt(
    bounds: str, handle: str, display_name: str, aliases: tuple[str, ...],
) -> str:
    names = ", ".join((display_name, *aliases))
    return _common(bounds) + f"""
\nDeep-search @{handle} ({names}). Return their own BSC meme posts with direct status URL,
exact CA and post time, especially posts before later price peaks. Also return only direct
sources for any DeBot/GMGN KOL label or full-wallet attribution. If none exist, say so;
do not substitute posts by other accounts or fabricate a match.
"""
