"""One authoritative priority rule for every narrative job source."""

from __future__ import annotations

from datetime import datetime, timedelta

from ..domain import DeBotSignal
from ..identity import utc_datetime, utc_now
from ..telegram.models import TelegramPost
from ..x.models import XPost
from .actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from .market_signal import MarketAnomaly


QUALIFIED_DEBOT_PRIORITY = 6
UNQUALIFIED_DEBOT_PRIORITY = 40
MARKET_ANOMALY_PRIORITY = 8
REALTIME_WINDOW = timedelta(minutes=2)
REPLAY_PRIORITY = 80


def narrative_job_priority(
    value: XPost | TelegramPost | DeBotSignal | MarketAnomaly,
    registry: ActorRegistry = DEFAULT_ACTOR_REGISTRY,
    *,
    now: datetime | None = None,
) -> int:
    """Rank live evidence first while retaining old replay work at low priority."""

    if isinstance(value, XPost):
        priority = registry.resolve(value.author).priority
        event_at = value.created_at
    elif isinstance(value, TelegramPost):
        actor = registry.resolve_telegram(value.channel)
        if actor is None:
            raise ValueError("unregistered Telegram channel cannot enter the queue")
        priority = actor.priority
        event_at = value.created_at
    elif isinstance(value, DeBotSignal):
        priority = (
            QUALIFIED_DEBOT_PRIORITY
            if value.kol_buy_qualified
            else UNQUALIFIED_DEBOT_PRIORITY
        )
        event_at = value.available_at
    elif isinstance(value, MarketAnomaly):
        priority = MARKET_ANOMALY_PRIORITY
        event_at = value.observed_at
    else:
        raise TypeError("unsupported narrative job payload")
    observed_at = utc_datetime(now if now is not None else utc_now())
    if observed_at - utc_datetime(event_at) > REALTIME_WINDOW:
        return max(priority, REPLAY_PRIORITY)
    return priority
