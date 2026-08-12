"""Infer provider-owned resource times without pretending they are observation times."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from urllib.parse import urlsplit


_TWITTER_EPOCH_MS = 1_288_834_974_657
_AVATAR_PATH = re.compile(r"^/profile_images/([1-9][0-9]{5,24})/")
_BANNER_PATH = re.compile(r"^/profile_banners/[1-9][0-9]{5,24}/([0-9]{9,12})(?:/|$)")


def twitter_snowflake_time(value: str | int) -> datetime:
    try:
        snowflake = int(value)
    except (TypeError, ValueError):
        raise ValueError("invalid Twitter snowflake") from None
    if snowflake <= 0:
        raise ValueError("invalid Twitter snowflake")
    milliseconds = (snowflake >> 22) + _TWITTER_EPOCH_MS
    return datetime.fromtimestamp(milliseconds / 1_000, timezone.utc)


def profile_resource_time(url: str) -> datetime | None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "pbs.twimg.com":
        return None
    avatar = _AVATAR_PATH.match(parsed.path)
    if avatar:
        return twitter_snowflake_time(avatar.group(1))
    banner = _BANNER_PATH.match(parsed.path)
    if banner:
        return datetime.fromtimestamp(int(banner.group(1)), timezone.utc)
    return None
