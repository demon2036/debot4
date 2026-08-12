"""Reviewed exact-CA KOL claims; outcome measurement remains outside this catalog."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KolTokenCase:
    handle: str
    tweet_id: str
    posted_at: int
    chain: str
    address: str
    token: str
    ca_evidence: str
    claim_stage: str = "candidate"
    published_peak_fdv_usd: int | None = None

    def __post_init__(self) -> None:
        address = self.address.casefold()
        if len(address) != 42 or not address.startswith("0x"):
            raise ValueError("KOL case requires exact EVM token CA")
        object.__setattr__(self, "address", address)

    @property
    def tweet_url(self) -> str:
        return f"https://x.com/{self.handle}/status/{self.tweet_id}"


KOL_TOKEN_CASES = (
    KolTokenCase(
        "btc2ai", "2086756263141245396", 1786356437, "robinhood",
        "0x9e722ee888bcc282a20f16b85ec1a48be15d32cf", "SPX6900", "tweet_text",
    ),
    KolTokenCase(
        "co_cobling", "2084114816856478177", 1785726667, "bsc",
        "0xfe189e97832da1573e4e4ff034f4ffc3a15c7777", "MarsCoin", "tweet_text",
    ),
    KolTokenCase(
        "CYaChoCho", "2086667129391390874", 1786335186, "robinhood",
        "0xe934e36a439c94017b64a3fece66af12099abf50", "STONKBROKER", "tweet_text",
        "self_disclosed_recap_from_95m_to_77m", 95_000_000,
    ),
    KolTokenCase(
        "CENTWT", "2077647640154775957", 1784184772, "robinhood",
        "0xa1e58d83493f2402e460180f3edf17a8f4ce11c2", "GREENBOW", "tweet_text",
    ),
    KolTokenCase(
        "CENTWT", "2077647640154775957", 1784184772, "robinhood",
        "0x894fac757250f8e02180e1856957274d84ac4ba3", "RHAGENT", "tweet_text",
    ),
    KolTokenCase(
        "CENTWT", "2077647640154775957", 1784184772, "robinhood",
        "0x3450598e419abb5609f60e4b2fda127ff0897777", "FLETCH", "tweet_text",
    ),
    KolTokenCase(
        "kenjiquest", "2086703666078081349", 1786343897, "robinhood",
        "0xe724485732d12c3ec6dba2176f55338eb2124ba3", "iHOOD",
        "wallet_transfer_and_token_holder_evidence", "candidate_after_wallet_disclosure",
    ),
    KolTokenCase(
        "stitchdegen", "2086912035904999818", 1786393576, "robinhood",
        "0x39dbed3a2bd333467115de45665cc57f813c4571", "PONS", "tweet_text",
        "late_thesis_after_prior_peak",
    ),
    KolTokenCase(
        "RobinhoodAlphas", "2086905840972529889", 1786392099, "robinhood",
        "0x49c62047965eafd1c0e09c4747242e9d3cbd6eb8", "KISMET", "tweet_text",
    ),
)


UNRESOLVED_KOL_CLAIMS = (
    {
        "handle": "yeonwoo1102",
        "tweet_id": "2086876192154800248",
        "posted_at": 1786385031,
        "token": "JACKET",
        "reason": "tweet_has_no_chain_specific_exact_ca_or_wallet",
    },
)
