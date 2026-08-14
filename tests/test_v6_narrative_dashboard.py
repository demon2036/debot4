from __future__ import annotations

from contextlib import contextmanager
import http.client
import json
from threading import Thread
from typing import Iterator
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from debot4.v6.narrative.dashboard import create_narrative_dashboard_server


STATUS = {
    "mode": "research_only",
    "research_only": True,
    "authorizes_trade": False,
    "profitability": "unknown",
    "jobs": {"total": 2, "counts": {"pending": 1}},
    "research": {"total": 1, "recent_packages": []},
    "actors": [],
}


@contextmanager
def _server(provider=lambda: STATUS) -> Iterator[object]:
    server = create_narrative_dashboard_server(provider, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _url(server: object, path: str) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}{path}"  # type: ignore[attr-defined]


def test_dashboard_serves_chinese_html_and_exact_read_only_status() -> None:
    with _server() as server:
        with urlopen(_url(server, "/api/status"), timeout=2) as response:  # noqa: S310
            assert response.status == 200
            assert json.loads(response.read()) == STATUS
            assert response.headers["Cache-Control"] == "no-store, max-age=0"
            assert response.headers["Cross-Origin-Resource-Policy"] == "same-origin"
            assert response.headers["X-Frame-Options"] == "DENY"
            assert response.headers.get("Access-Control-Allow-Origin") is None

        with urlopen(_url(server, "/"), timeout=2) as response:  # noqa: S310
            html = response.read().decode("utf-8")
        assert "叙事研究状态" in html
        assert "不授权交易" in html
        assert "X 实时互动测试" in html
        assert "15 秒 推文→Mint 报警" in html
        assert "裸 mint、RPC 和模型均不触发报警" in html
        assert "点赞不可见" in html
        assert "/api/status" in html


def test_dashboard_supports_head_but_rejects_every_write_method() -> None:
    with _server() as server:
        request = Request(_url(server, "/api/status"), method="HEAD")
        with urlopen(request, timeout=2) as response:  # noqa: S310
            assert response.status == 200
            assert response.read() == b""
            assert int(response.headers["Content-Length"]) > 0

        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            request = Request(
                _url(server, "/api/status"), data=b"{}", method=method
            )
            with pytest.raises(HTTPError) as caught:
                urlopen(request, timeout=2)  # noqa: S310
            assert caught.value.code == 405
            assert caught.value.headers["Allow"] == "GET, HEAD"
            body = json.loads(caught.value.read())
            assert body["read_only"] is True
            assert body["authorizes_trade"] is False


def test_cross_site_reads_are_rejected_and_provider_is_not_called() -> None:
    calls = 0

    def provider():
        nonlocal calls
        calls += 1
        return STATUS

    with _server(provider) as server:
        request = Request(
            _url(server, "/api/status"), headers={"Origin": "https://evil.test"}
        )
        with pytest.raises(HTTPError) as caught:
            urlopen(request, timeout=2)  # noqa: S310
        assert caught.value.code == 403
        assert calls == 0


def test_server_defaults_to_loopback_and_refuses_public_binding() -> None:
    with _server() as server:
        assert server.server_address[0] == "127.0.0.1"  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="loopback"):
        create_narrative_dashboard_server(lambda: STATUS, host="0.0.0.0")


def test_provider_failure_is_sanitized() -> None:
    def broken():
        raise RuntimeError("secret-key-should-not-leak")

    with _server(broken) as server:
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_address[1], timeout=2  # type: ignore[attr-defined]
        )
        connection.request("GET", "/api/status")
        response = connection.getresponse()
        body = response.read()
        connection.close()
    assert response.status == 503
    assert b"secret-key-should-not-leak" not in body
    assert json.loads(body)["authorizes_trade"] is False
