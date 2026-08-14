"""Bounded omission sweeps for Chinese BSC KOL lead discovery."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable


SearchSpec = tuple[str, str, str]


def omission_sweeps(bounds: str, common: str) -> tuple[SearchSpec, ...]:
    prompts = {
        "bsc-alpha-circles": """
Find Chinese-language BSC meme alpha callers beyond the supplied directories. Search
BNB meme, 金狗, 喊单, 链上打狗, 聪明钱, 内盘 and early-call wording. Return direct profile
and authored status URLs, including small accounts; distinguish scanners and projects.
""",
        "nickname-handle-changes": """
Find nickname variants, renamed handles and stable profile clues for Chinese meme
callers. Search replies that literally map old and new names. Never merge two people by
a similar display name; return every plausible direct profile and source status.
""",
        "ranking-image-directories": """
Find public rankings, follow lists, screenshots and image directories of Chinese meme
traders or callers. Return the original list post and direct profiles literally shown;
label self-promotion, fan nomination and performance claims as unverified.
""",
        "reply-quote-network": """
Snowball through replies, quotes and mentions around verified Chinese BSC alpha accounts.
Find additional authored exact-CA callers and preserve the direct post URL. Do not turn a
reply, scanner alert, copied contract or project announcement into an original call.
""",
        "hk-tw-sg-chinese": """
Search Traditional-Chinese and mixed Chinese/English BSC meme circles in Hong Kong,
Taiwan, Singapore and diaspora communities. Return direct profile and authored status
URLs even when no public wallet exists; preserve aliases and role uncertainty.
""",
        "provider-bound-profiles": """
Find public GMGN or DeBot KOL profile pages and screenshots that expose a bound X handle
for BSC meme traders. A provider label is only a lead. Return direct X profiles and the
provider source, and never infer a wallet or ownership from a display name.
""",
        "public-shadow-attribution": """
Find published evidence of secondary X accounts or secondary wallets attributed to major
Chinese meme callers. Accept only direct self-disclosure, signed proof, provider-bound
profiles or named investigations. One days-early buy may be relevant and need not repeat;
timing alone never proves ownership.
""",
    }
    return tuple(
        (f"omission:{key}", "x" if key != "public-shadow-attribution" else "discovery",
         common + text)
        for key, text in prompts.items()
    )


def period_sweeps(
    start: date,
    end_exclusive: date,
    common_factory: Callable[[str], str],
) -> tuple[SearchSpec, ...]:
    tasks = []
    cursor = start
    while cursor < end_exclusive:
        boundary = min(cursor + timedelta(days=91), end_exclusive)
        bounds = f"UTC [{cursor.isoformat()}, {boundary.isoformat()})"
        prompt = common_factory(bounds) + """
\nCarpet-search this bounded period for Chinese-authored BSC meme posts containing a
literal 0x token contract before or during a move. Return every direct status and profile
URL found, including small callers. Classify original thesis, own position, relay,
scanner, project post, warning and recap separately. Do not require a public wallet.
"""
        tasks.append((f"period:{cursor}:{boundary}", "x", prompt))
        cursor = boundary
    return tuple(tasks)
