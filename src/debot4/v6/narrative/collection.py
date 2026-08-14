"""Fast, durable collection for every narrative discovery source."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from threading import Lock

from ..debot.ranks_models import RankSnapshot
from ..identity import utc_now
from ..telegram.models import TelegramPost
from ..x.models import XPost
from .actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from .catalyst_mint import CatalystMintMatch
from .catalyst_mint_state import CatalystMintState
from .collection_sources import (
    ChainMintSource,
    DeBotSource,
    MarketSource,
    MintSource,
    TelegramSource,
    XSource,
)
from .debot_feed import NarrativeDeBotCandidate
from .debot_mint_location import location_from_debot
from .job_priority import narrative_job_priority
from .job_queue import NarrativeJobQueue
from .live_signal_filter import (
    AllowAllSignalFilter,
    NarrativeSignal,
    NarrativeSignalFilter,
    SignalFilterDecision,
)
from .market_signal import MarketAnomaly
from .mint_alert_store import MintAlertStore
from .mint_collection import MintCollectionPipeline
from .mint_location import MintLocation
from .mint_location_store import MintLocationStore


@dataclass(frozen=True, slots=True)
class CollectionCycle:
    x_posts: int
    telegram_posts: int
    debot_signals: int
    market_anomalies: int = 0
    catalyst_mint_matches: int = 0
    mint_locations: int = 0

    @property
    def active_posts(self) -> int:
        return self.x_posts

    @property
    def passive_signals(self) -> int:
        return (
            self.debot_signals + self.market_anomalies
            + self.catalyst_mint_matches
        )


class NarrativeCollector:
    """Persist source items before their source checkpoint is advanced."""

    def __init__(
        self,
        monitor: XSource,
        telegram_monitor: TelegramSource,
        debot_feed: DeBotSource,
        queue: NarrativeJobQueue,
        *,
        market_monitor: MarketSource | None = None,
        mint_monitor: MintSource | None = None,
        catalyst_mints: CatalystMintState | None = None,
        chain_mint_monitor: ChainMintSource | None = None,
        mint_locations: MintLocationStore | None = None,
        mint_alerts: MintAlertStore | None = None,
        max_attempts: int = 3,
        registry: ActorRegistry = DEFAULT_ACTOR_REGISTRY,
        clock: Callable[[], datetime] = utc_now,
        signal_filter: NarrativeSignalFilter | None = None,
    ) -> None:
        if isinstance(max_attempts, bool) or not 1 <= max_attempts <= 100:
            raise ValueError("max_attempts must be between 1 and 100")
        self.monitor = monitor
        self.telegram_monitor = telegram_monitor
        self.debot_feed = debot_feed
        self.market_monitor = market_monitor
        if catalyst_mints is not None and mint_monitor is None:
            raise ValueError("catalyst state requires the DeBot mint monitor")
        if (
            (mint_monitor is not None or chain_mint_monitor is not None)
            and mint_locations is None
        ):
            raise ValueError("mint sources require durable mint location storage")
        if (catalyst_mints is None) != (mint_alerts is None):
            raise ValueError("catalyst state and mint alert storage must be paired")
        self.mint_monitor = mint_monitor
        self.catalyst_mints = catalyst_mints
        self.chain_mint_monitor = chain_mint_monitor
        self.mint_alerts = mint_alerts
        self._mint_pipeline = MintCollectionPipeline(mint_locations)
        self.queue = queue
        self.max_attempts = max_attempts
        self.registry = registry
        self.clock = clock
        self.signal_filter = signal_filter or AllowAllSignalFilter()
        self._filter_counts: Counter[tuple[bool, str]] = Counter()
        self._filter_lock = Lock()

    def collect_once(self) -> CollectionCycle:
        x_posts = self.collect_x_once()
        telegram_posts = self.collect_telegram_once()
        candidates = self.collect_debot_once()
        anomalies = self.collect_market_once()
        matches = self.collect_mints_once()
        self.collect_chain_mints_once()
        return CollectionCycle(
            len(x_posts), len(telegram_posts), len(candidates), len(anomalies),
            len(matches), self._mint_pipeline.cycle_inserted(),
        )

    def collect_x_once(self) -> tuple[XPost, ...]:
        return self.monitor.monitor_once(accept=self._accept_x)

    def collect_telegram_once(self) -> tuple[TelegramPost, ...]:
        return self.telegram_monitor.monitor_once(accept=self.accept_telegram)

    def collect_debot_once(self) -> tuple[NarrativeDeBotCandidate, ...]:
        return self.debot_feed.poll_once(accept=self._accept_debot)

    def collect_market_once(self) -> tuple[MarketAnomaly, ...]:
        if self.market_monitor is None:
            return ()
        return self.market_monitor.poll_once(accept=self._accept_market)

    def collect_mints_once(self) -> tuple[CatalystMintMatch, ...]:
        if self.mint_monitor is None:
            return ()
        self._mint_pipeline.reset_cycle_source(chain=False)
        accepted: list[CatalystMintMatch] = []

        def consume(snapshots: tuple[RankSnapshot, ...]) -> None:
            accepted.extend(self._accept_mints(snapshots))

        self.mint_monitor.poll_once(accept=consume)
        return tuple(accepted)

    def collect_chain_mints_once(self) -> tuple[MintLocation, ...]:
        if self.chain_mint_monitor is None:
            return ()
        self._mint_pipeline.reset_cycle_source(chain=True)
        return self.chain_mint_monitor.poll_once(
            accept=self._accept_chain_mints
        )

    def filter_snapshot(self) -> dict[str, object]:
        with self._filter_lock:
            counts = dict(self._filter_counts)
        accepted = sum(total for (keep, _), total in counts.items() if keep)
        rejected = sum(total for (keep, _), total in counts.items() if not keep)
        return {
            "accepted": accepted,
            "rejected": rejected,
            "reasons": {
                reason: total
                for (_, reason), total in sorted(
                    counts.items(), key=lambda item: item[0]
                )
            },
        }

    def mint_pipeline_snapshot(self) -> dict[str, object]:
        filtering = self.filter_snapshot()
        snapshot = self._mint_pipeline.snapshot(int(filtering["accepted"]))
        snapshot["mint_alerts"] = (
            {"configured": False, "total": 0, "pending_delivery": 0}
            if self.mint_alerts is None
            else {"configured": True, **self.mint_alerts.snapshot()}
        )
        return snapshot

    def _enqueue(
        self,
        payload: NarrativeSignal,
        *,
        before_queue: Callable[[NarrativeSignal], None] | None = None,
    ) -> bool:
        decision = self.signal_filter.decide(payload)
        if not decision.accepted:
            self._record_filter(decision)
            return False
        if before_queue is not None:
            before_queue(payload)
        self.queue.enqueue(
            payload,
            max_attempts=self.max_attempts,
            priority=narrative_job_priority(
                payload, self.registry, now=self.clock()
            ),
        )
        self._record_filter(decision)
        return True

    def _record_filter(self, decision: SignalFilterDecision) -> None:
        with self._filter_lock:
            self._filter_counts[(decision.accepted, decision.reason)] += 1

    def _accept_x(self, posts: tuple[XPost, ...]) -> None:
        if posts and self.catalyst_mints is not None:
            self._persist_matches(self.catalyst_mints.observe_posts(posts))
        for post in posts:
            self._enqueue(post)

    def accept_telegram(self, posts: tuple[TelegramPost, ...]) -> None:
        """Persist realtime or public Telegram observations idempotently."""

        for post in posts:
            self._enqueue(post)

    def _accept_debot(
        self, candidates: tuple[NarrativeDeBotCandidate, ...]
    ) -> None:
        for candidate in candidates:
            self._enqueue(candidate.signal)

    def _accept_market(self, anomalies: tuple[MarketAnomaly, ...]) -> None:
        for anomaly in anomalies:
            self._enqueue(anomaly)

    def _accept_mints(
        self, snapshots: tuple[RankSnapshot, ...]
    ) -> tuple[CatalystMintMatch, ...]:
        locations = tuple(location_from_debot(item) for item in snapshots)
        self._record_locations(locations, chain=False)
        if self.catalyst_mints is None:
            return ()
        return self._persist_matches(self.catalyst_mints.observe_mints(snapshots))

    def _accept_chain_mints(
        self, locations: tuple[MintLocation, ...]
    ) -> None:
        self._record_locations(locations, chain=True)

    def _record_locations(
        self, locations: tuple[MintLocation, ...], *, chain: bool,
    ) -> None:
        self._mint_pipeline.record(locations, chain=chain)

    def _persist_matches(
        self, matches: tuple[CatalystMintMatch, ...]
    ) -> tuple[CatalystMintMatch, ...]:
        accepted = tuple(
            match
            for match in matches
            if self._enqueue(match, before_queue=self._record_mint_alert)
        )
        self._mint_pipeline.record_hard_bindings(len(accepted))
        if matches and self.catalyst_mints is not None:
            self.catalyst_mints.acknowledge(match.match_id for match in matches)
        return accepted

    def _record_mint_alert(self, signal: NarrativeSignal) -> None:
        if not isinstance(signal, CatalystMintMatch):
            raise TypeError("only catalyst mint matches may create mint alerts")
        if self.mint_alerts is None:
            raise RuntimeError("mint alert persistence is unavailable")
        self.mint_alerts.record((signal,))
