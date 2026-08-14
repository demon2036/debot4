from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from debot4.v6.narrative import cli
from debot4.v6.narrative.job_queue_models import JobStatus
from debot4.v6.narrative.service import CollectionCycle, WorkCycle


class FakeQueue:
    def counts(self) -> dict[JobStatus, int]:
        return {
            JobStatus.PENDING: 2,
            JobStatus.LEASED: 0,
            JobStatus.DONE: 4,
            JobStatus.FAILED: 1,
        }


class FakeStore:
    def count(self) -> int:
        return 7


class FakeApp:
    def __init__(self, *, research: bool, wait_for_stop: bool = False) -> None:
        self.research = research
        self.wait_for_stop = wait_for_stop
        self.queue = FakeQueue()
        self.research_store = FakeStore() if research else None
        self.collector = SimpleNamespace(
            filter_snapshot=lambda: {
                "accepted": 3,
                "rejected": 2,
                "reasons": {"test": 5},
            },
            mint_pipeline_snapshot=lambda: {
                "narrative_signals_queued": 3,
                "mint_locations": {"unique_exact_cas": 2},
                "mint_alerts": {"total": 2, "pending_delivery": 0},
                "hard_catalyst_bindings_queued": 0,
            },
        )
        self.mint_alert_dispatcher = SimpleNamespace(
            snapshot=lambda: {"delivered": 2}
        )
        self.service = SimpleNamespace(
            last_collector_error_type=None,
            last_source_error_types={"x": None, "debot": None},
            last_worker_error_type="GrokApiError",
            last_worker_error_types={"grok-1": "GrokApiError"},
            workers=(object(), object()),
            last_realtime_error_type=None,
        )
        self.telegram_realtime = None
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        self.closed = True

    def collect_once(self) -> CollectionCycle:
        return CollectionCycle(3, 2, 5)

    def work_once(self) -> WorkCycle:
        return WorkCycle("job-1", JobStatus.DONE, 1)

    def run(self, stop: object) -> None:
        if self.wait_for_stop:
            assert stop.wait(1)


def _output(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_collect_once_is_json_and_does_not_request_grok(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    built: list[FakeApp] = []

    def build(*, research: bool) -> FakeApp:
        app = FakeApp(research=research)
        built.append(app)
        return app

    monkeypatch.setattr(cli, "build_narrative_app", build)

    assert cli.main(["collect-once"]) == 0

    assert built[0].research is False and built[0].closed is True
    assert _output(capsys) == {
        "ok": True,
        "command": "collect-once",
        "x_posts": 3,
        "telegram_posts": 2,
            "debot_signals": 5,
        "market_anomalies": 0,
        "catalyst_mint_matches": 0,
        "mint_locations": 0,
        "mint_pipeline": {
            "narrative_signals_queued": 3,
            "mint_locations": {"unique_exact_cas": 2},
            "mint_alerts": {"total": 2, "pending_delivery": 0},
            "hard_catalyst_bindings_queued": 0,
        },
        "filter": {"accepted": 3, "rejected": 2, "reasons": {"test": 5}},
        "jobs": {"pending": 2, "leased": 0, "done": 4, "failed": 1},
    }


def test_work_once_requires_full_runtime_and_reports_durable_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    built: list[FakeApp] = []

    def build(*, research: bool) -> FakeApp:
        app = FakeApp(research=research)
        built.append(app)
        return app

    monkeypatch.setattr(cli, "build_narrative_app", build)

    assert cli.main(["work-once"]) == 0

    assert built[0].research is True and built[0].closed is True
    output = _output(capsys)
    assert output["job_id"] == "job-1"
    assert output["status"] == "done"
    assert output["attempts"] == 1
    assert output["idle"] is False
    assert output["research_packages"] == 7


def test_run_max_seconds_stops_and_closes_cleanly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    built: list[FakeApp] = []

    def build(*, research: bool) -> FakeApp:
        app = FakeApp(research=research, wait_for_stop=True)
        built.append(app)
        return app

    monkeypatch.setattr(cli, "build_narrative_app", build)

    assert cli.main(["run", "--max-seconds", "0.01"]) == 0

    assert built[0].closed is True
    output = _output(capsys)
    assert output["stopped_by"] == "max_seconds"
    assert output["collector_error_type"] is None
    assert output["source_error_types"] == {"x": None, "debot": None}
    assert output["worker_error_type"] == "GrokApiError"
    assert output["worker_error_types"] == {"grok-1": "GrokApiError"}
    assert output["research_workers"] == 2
    assert output["filter"]["rejected"] == 2
    assert output["telegram_realtime"]["status"] == "disabled"


def test_failures_emit_only_safe_type_and_reason(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(**_kwargs: object) -> FakeApp:
        raise RuntimeError("Bearer top-secret at https://private.invalid")

    monkeypatch.setattr(cli, "build_narrative_app", fail)

    assert cli.main(["work-once"]) == 1

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "top-secret" not in captured.out
    assert "private.invalid" not in captured.out
    assert json.loads(captured.out) == {
        "ok": False,
        "error": {
            "type": "RuntimeError",
            "reason": "narrative operation failed",
        },
    }


def test_invalid_arguments_are_also_json_and_do_not_echo_input(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["run", "--max-seconds", "secret-value"]) == 2

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "secret-value" not in captured.out
    assert json.loads(captured.out)["error"] == {
        "type": "CliUsageError",
        "reason": "narrative configuration or input is invalid",
    }
