"""JSON-only CLI for the independent v6 narrative service."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import math
import signal
import sys
from threading import Event, Timer, current_thread, main_thread
from typing import Iterator, Sequence

from ..x import XProfileClient
from .app import NarrativeApp, build_narrative_app
from .actor_evidence import ActorEvidenceCandidate, verify_actor_evidence
from .fxtwitter import FxTwitterClient
from .job_queue_models import JobStatus


class CliUsageError(ValueError):
    """A command-line shape error whose details are intentionally not echoed."""


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise CliUsageError("invalid narrative command")


def _build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(
        prog="python -m debot4.v6.narrative.cli",
        description="Collect and research v6 narrative signals.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser(
        "collect-once",
        help="poll X, Telegram, DeBot, and BSC gainers without requiring Grok",
    )
    collect.set_defaults(handler=_cmd_collect_once)
    work = commands.add_parser(
        "work-once", help="research at most one queued item through Grok"
    )
    work.set_defaults(handler=_cmd_work_once)
    verify = commands.add_parser(
        "verify-actor-evidence",
        help="verify one model-discovered X status before catalog onboarding",
    )
    verify.add_argument("--handle", required=True)
    verify.add_argument("--status-url", required=True)
    verify.set_defaults(handler=_cmd_verify_actor_evidence)
    run = commands.add_parser(
        "run", help="run fast collection and narrative research until stopped"
    )
    run.add_argument(
        "--max-seconds",
        type=_non_negative_seconds,
        default=None,
        metavar="SECONDS",
        help="optional bounded runtime; omitted means run until SIGINT/SIGTERM",
    )
    run.set_defaults(handler=_cmd_run)
    return parser


def _non_negative_seconds(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a non-negative number") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative finite number")
    return parsed


def _cmd_collect_once(_args: argparse.Namespace) -> dict[str, object]:
    with build_narrative_app(research=False) as app:
        cycle = app.collect_once()
        return {
            "ok": True,
            "command": "collect-once",
            "x_posts": cycle.x_posts,
            "telegram_posts": cycle.telegram_posts,
            "debot_signals": cycle.debot_signals,
            "market_anomalies": cycle.market_anomalies,
            "filter": app.collector.filter_snapshot(),
            "jobs": _queue_counts(app),
        }


def _cmd_work_once(_args: argparse.Namespace) -> dict[str, object]:
    with build_narrative_app(research=True) as app:
        cycle = app.work_once()
        return {
            "ok": True,
            "command": "work-once",
            "idle": cycle.idle,
            "job_id": cycle.job_id,
            "status": None if cycle.status is None else cycle.status.value,
            "attempts": cycle.attempts,
            "jobs": _queue_counts(app),
            "research_packages": _research_count(app),
        }


def _cmd_verify_actor_evidence(args: argparse.Namespace) -> dict[str, object]:
    finding = verify_actor_evidence(
        ActorEvidenceCandidate(args.handle, args.status_url),
        profiles=XProfileClient(),
        statuses=FxTwitterClient(),
    )
    return {
        "ok": finding.verified,
        "command": "verify-actor-evidence",
        "status": finding.status,
        "claimed_handle": finding.claimed_handle,
        "observed_handle": finding.observed_handle,
        "observed_author_id": finding.observed_author_id,
        "profile_user_id": finding.profile_user_id,
        "canonical_url": finding.canonical_url,
        "text": finding.text[:1_000],
        "error_type": finding.error_type,
    }


def _cmd_run(args: argparse.Namespace) -> dict[str, object]:
    stop = Event()
    reason = {"value": "service_returned"}
    timer: Timer | None = None
    with build_narrative_app(research=True) as app:
        with _signal_stop(stop, reason):
            if args.max_seconds is not None:
                if args.max_seconds == 0:
                    reason["value"] = "max_seconds"
                    stop.set()
                else:
                    timer = Timer(
                        args.max_seconds,
                        _timed_stop,
                        args=(stop, reason),
                    )
                    timer.daemon = True
                    timer.start()
            try:
                app.run(stop)
            finally:
                if timer is not None:
                    timer.cancel()
        return {
            "ok": True,
            "command": "run",
            "stopped_by": reason["value"],
            "collector_error_type": app.service.last_collector_error_type,
            "source_error_types": app.service.last_source_error_types,
            "worker_error_type": app.service.last_worker_error_type,
            "worker_error_types": app.service.last_worker_error_types,
            "research_workers": len(app.service.workers),
            "telegram_realtime_error_type": (
                app.service.last_realtime_error_type
            ),
            "telegram_realtime": _telegram_realtime_status(app),
            "filter": app.collector.filter_snapshot(),
            "jobs": _queue_counts(app),
            "research_packages": _research_count(app),
        }


def _timed_stop(stop: Event, reason: dict[str, str]) -> None:
    reason["value"] = "max_seconds"
    stop.set()


@contextmanager
def _signal_stop(stop: Event, reason: dict[str, str]) -> Iterator[None]:
    previous: dict[signal.Signals, object] = {}
    if current_thread() is main_thread():
        def request_stop(signum: int, _frame: object) -> None:
            reason["value"] = signal.Signals(signum).name.lower()
            stop.set()

        for item in (signal.SIGINT, signal.SIGTERM):
            previous[item] = signal.getsignal(item)
            signal.signal(item, request_stop)
    try:
        yield
    finally:
        for item, handler in previous.items():
            signal.signal(item, handler)


def _queue_counts(app: NarrativeApp) -> dict[str, int]:
    counts = app.queue.counts()
    return {status.value: int(counts.get(status, 0)) for status in JobStatus}


def _research_count(app: NarrativeApp) -> int:
    return 0 if app.research_store is None else app.research_store.count()


def _telegram_realtime_status(app: NarrativeApp) -> dict[str, object]:
    if app.telegram_realtime is None:
        return {
            "status": "disabled",
            "configured_channels": 0,
            "watched_channels": 0,
            "events_received": 0,
            "last_event_at": None,
            "last_error_type": None,
        }
    return app.telegram_realtime.snapshot().as_public_dict()


def _safe_error(exc: BaseException) -> dict[str, object]:
    if isinstance(exc, KeyboardInterrupt):
        reason = "narrative command was interrupted"
    elif isinstance(exc, (CliUsageError, ValueError, TypeError)):
        reason = "narrative configuration or input is invalid"
    elif isinstance(exc, (FileNotFoundError, PermissionError, OSError)):
        reason = "narrative local state is unavailable"
    else:
        reason = "narrative operation failed"
    return {
        "ok": False,
        "error": {"type": type(exc).__name__, "reason": reason},
    }


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.write(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _build_parser().parse_args(argv)
        result = args.handler(args)
    except KeyboardInterrupt as exc:
        _emit(_safe_error(exc))
        return 130
    except Exception as exc:
        _emit(_safe_error(exc))
        return 2 if isinstance(exc, CliUsageError) else 1
    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
