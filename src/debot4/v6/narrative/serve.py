"""Run the narrative collectors, Grok worker, and loopback dashboard together."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import signal
import sys
from threading import Event, current_thread, main_thread
from typing import Iterator, Sequence

from .app import build_narrative_app
from .dashboard import NarrativeDashboard
from .runtime_status import app_status_snapshot
from .settings import NarrativeSettings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m debot4.v6.narrative.serve",
        description="Run DeBot narrative research with a loopback dashboard.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=_port, default=8777)
    return parser


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65_535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


@contextmanager
def _signal_stop(stop: Event) -> Iterator[None]:
    previous: dict[signal.Signals, object] = {}
    if current_thread() is main_thread():
        def request_stop(_signum: int, _frame: object) -> None:
            stop.set()

        for item in (signal.SIGINT, signal.SIGTERM):
            previous[item] = signal.getsignal(item)
            signal.signal(item, request_stop)
    try:
        yield
    finally:
        for item, handler in previous.items():
            signal.signal(item, handler)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = NarrativeSettings.from_env()
    stop = Event()
    dashboard: NarrativeDashboard | None = None
    try:
        with build_narrative_app(settings, research=True) as app:
            dashboard = NarrativeDashboard(
                lambda: app_status_snapshot(app), host=args.host, port=args.port
            )
            dashboard.start()
            host, port = dashboard.address
            sys.stdout.write(json.dumps({
                "ok": True,
                "dashboard_url": f"http://{host}:{port}",
                "research_only": True,
                "authorizes_trade": False,
            }, ensure_ascii=False, sort_keys=True) + "\n")
            sys.stdout.flush()
            with _signal_stop(stop):
                app.run(stop)
    except KeyboardInterrupt:
        stop.set()
        return 130
    finally:
        if dashboard is not None:
            dashboard.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
