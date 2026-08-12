"""Pure reviewed identity and wallet-attribution records for KOL research."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .models import normalize_evm_address


_HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}")
_USER_ID = re.compile(r"[1-9][0-9]{5,24}")


class IdentityTier(str, Enum):
    CANDIDATE = "candidate"
    X_VERIFIED = "x_verified"
    WALLET_ATTRIBUTED = "wallet_attributed"


@dataclass(frozen=True, slots=True)
class KolIdentity:
    handle: str
    stable_user_id: str
    display_name: str
    aliases: tuple[str, ...]
    tier: IdentityTier
    evidence_urls: tuple[str, ...]
    wallet: str | None = None
    attribution_url: str | None = None

    def __post_init__(self) -> None:
        handle = self.handle.strip().lstrip("@")
        if not _HANDLE.fullmatch(handle) or not _USER_ID.fullmatch(self.stable_user_id):
            raise ValueError("KOL identity requires a stable X identity")
        if not self.display_name.strip() or not self.evidence_urls:
            raise ValueError("KOL identity evidence is incomplete")
        if any(not value.startswith("https://") for value in self.evidence_urls):
            raise ValueError("KOL identity evidence URLs must use HTTPS")
        wallet = normalize_evm_address(self.wallet) if self.wallet else None
        attributed = self.tier is IdentityTier.WALLET_ATTRIBUTED
        if attributed != bool(wallet and self.attribution_url):
            raise ValueError("wallet attribution needs a wallet and source URL")
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "display_name", self.display_name.strip())
        object.__setattr__(self, "aliases", tuple(dict.fromkeys(self.aliases)))
        object.__setattr__(self, "evidence_urls", tuple(dict.fromkeys(self.evidence_urls)))
        object.__setattr__(self, "wallet", wallet)


LOOKONCHAIN_BSC_TRADERS = (
    KolIdentity(
        "hexiecs", "1236194290100928514", "冷静冷静再冷静", ("冷静",),
        IdentityTier.WALLET_ATTRIBUTED,
        ("https://x.com/hexiecs",),
        "0xeb89055e16ae1c1e42ad6770a7344ff5c7b4f31d",
        "https://x.com/lookonchain/status/1975782365650952370",
    ),
    KolIdentity(
        "brc20niubi", "1332902969273065473", "王小二", ("王小二",),
        IdentityTier.WALLET_ATTRIBUTED,
        ("https://x.com/brc20niubi",),
        "0x176e6378b7c9010f0456bee76ce3039d36dc37c8",
        "https://x.com/lookonchain/status/1975782365650952370",
    ),
    KolIdentity(
        "GCsheng", "1344963706657017858", "深大高财生.milady",
        ("深大高财生", "深大高材生", "深大"), IdentityTier.WALLET_ATTRIBUTED,
        ("https://x.com/GCsheng", "https://x.com/GCsheng/status/2064388171040010417"),
        "0x51fbb0b8164231c116acdce55db3d5c0d9650987",
        "https://x.com/lookonchain/status/1975782365650952370",
    ),
)


CHINESE_MEME_KOL_CANDIDATES = tuple(
    KolIdentity(
        handle, user_id, name, (), IdentityTier.X_VERIFIED,
        (f"https://x.com/{handle}", "https://x.com/facai988/status/1982437570467504565"),
    )
    for handle, user_id, name in (
        ("traderpow", "1325739682752204800", "pow🧲"),
        ("Ga__ke", "86647812", "gake"),
        ("0xcryptowizard", "1195728139898376193", "0xWizard"),
        ("CryptoDevinL", "1371263177288130561", "CryptoD"),
        ("BitCloutCat", "1374985535169552388", "LaserCat397.eth2.0"),
        ("aa_AFeng", "1303033822339104770", "阿峰_Afeng"),
        ("zhuilong888", "1785592993317318656", "蛙丑丑"),
        ("Ed_x0101", "1359150440663949319", "Ed_x區塊日記"),
        ("EnHeng456", "1509912900038582272", "EnHeng嗯哼.Ai"),
        ("monkeyjiang", "1954166149", "猴哥"),
        ("3ethtomoon", "1482768180699439109", "0xLeaf"),
        ("blknoiz06", "973261472", "Ansem"),
        ("0xSleepinRain", "1458399185490046977", "雨中狂睡"),
        ("SuperL9", "594717639", "Wick李"),
        ("19ys_GGboy", "1457789697556631552", "十九岁绿帽少年"),
        ("huigendeshen", "1806508121986314240", "侥幸哥"),
        ("0xSunNFT", "1146492710582308864", "0xSun"),
        ("kaikaibtc", "1576573316113965061", "K三 凯"),
        ("xiaomucrypto", "1791428022521741312", "海力士"),
        ("nancy_c813", "798785588048470017", "Nancy"),
        ("cishanjia", "1002945631407702017", "慈善家"),
        ("wolfyxbt", "1516941936971554817", "杀破狼 WolfyXBT"),
        ("Crypto_Cat888", "1632296925826543618", "LazyCat 猫姐"),
        ("CindyCreation", "1058197676213231618", "Cindy胖迪"),
    )
)
