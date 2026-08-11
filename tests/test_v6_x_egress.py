from __future__ import annotations

from pathlib import Path
import urllib.error
import urllib.request

import pytest

from debot4.v6.x import FxEgressError, FxEgressNode, FxEgressPool


class FakeOpener:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls = 0

    def open(self, _request: object, *, timeout: float) -> object:
        assert timeout > 0
        self.calls += 1
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def _nodes() -> tuple[FxEgressNode, ...]:
    return (
        FxEgressNode("warp-01", "127.0.0.1", 11201),
        FxEgressNode("warp-02", "127.0.0.1", 11202),
        FxEgressNode("warp-03", "127.0.0.1", 11203),
    )


def test_round_robin_routes_each_request_to_the_next_node() -> None:
    openers: dict[str, FakeOpener] = {}

    def factory(node: FxEgressNode) -> FakeOpener:
        opener = FakeOpener(node.node_id)
        openers[node.node_id] = opener
        return opener

    pool = FxEgressPool(_nodes(), max_attempts=2, opener_factory=factory)
    request = urllib.request.Request("https://api.fxtwitter.com/test")

    assert pool.open(request, timeout=1) == "warp-01"
    assert pool.open(request, timeout=1) == "warp-02"
    assert pool.open(request, timeout=1) == "warp-03"
    assert [openers[key].calls for key in openers] == [1, 1, 1]


def test_transport_failure_uses_the_next_node_and_records_health() -> None:
    outcomes = {
        "warp-01": urllib.error.URLError("private endpoint must not leak"),
        "warp-02": "ok",
        "warp-03": "unused",
    }
    pool = FxEgressPool(
        _nodes(),
        max_attempts=3,
        opener_factory=lambda node: FakeOpener(outcomes[node.node_id]),
    )

    assert pool.open(
        urllib.request.Request("https://api.fxtwitter.com/test"), timeout=1
    ) == "ok"

    snapshot = pool.snapshot()
    assert snapshot["configured_nodes"] == 3
    assert snapshot["nodes"][0] == {
        "id": "warp-01",
        "attempts": 1,
        "successes": 0,
        "failures": 1,
        "last_error_type": "URLError",
    }
    assert snapshot["nodes"][1]["successes"] == 1
    assert "private endpoint" not in str(snapshot)


def test_all_failed_nodes_raise_a_sanitized_error() -> None:
    pool = FxEgressPool(
        _nodes(),
        max_attempts=2,
        opener_factory=lambda _node: FakeOpener(
            urllib.error.URLError("sensitive upstream detail")
        ),
    )

    with pytest.raises(FxEgressError, match="all configured") as caught:
        pool.open(
            urllib.request.Request("https://api.fxtwitter.com/test"), timeout=1
        )
    assert "sensitive upstream detail" not in str(caught.value)


def test_toml_selects_local_or_remote_endpoints(tmp_path: Path) -> None:
    config = tmp_path / "egress.toml"
    config.write_text(
        'schema = "debot4.egress_pool.v1"\n'
        '[[nodes]]\nid = "warp-01"\n'
        'local_url = "socks5h://127.0.0.1:11201"\n'
        'remote_url = "socks5h://172.18.0.1:21201"\n',
        encoding="utf-8",
    )
    seen: list[tuple[str, int]] = []

    def factory(node: FxEgressNode) -> FakeOpener:
        seen.append((node.proxy_host, node.proxy_port))
        return FakeOpener("ok")

    FxEgressPool.from_toml(
        config, location="remote", max_attempts=1, opener_factory=factory
    )

    assert seen == [("172.18.0.1", 21201)]


@pytest.mark.parametrize(
    "endpoint",
    (
        "http://127.0.0.1:11201",
        "socks5h://user:pass@127.0.0.1:11201",
        "socks5h://127.0.0.1:11201/path",
    ),
)
def test_toml_rejects_unsafe_proxy_urls(
    tmp_path: Path, endpoint: str
) -> None:
    config = tmp_path / "egress.toml"
    config.write_text(
        'schema = "debot4.egress_pool.v1"\n'
        '[[nodes]]\nid = "warp-01"\n'
        f'local_url = "{endpoint}"\n'
        'remote_url = "socks5h://172.18.0.1:21201"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="proxy URL"):
        FxEgressPool.from_toml(config, max_attempts=1)
