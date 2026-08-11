"""Loopback-only HTTP dashboard for narrative research status."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
import json
from threading import Thread
from typing import Any
from urllib.parse import urlsplit

from .dashboard_page import DASHBOARD_HTML
from .status import status_snapshot


StatusProvider = Callable[[], Mapping[str, Any]]


def create_narrative_dashboard_server(
    provider: StatusProvider = status_snapshot,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> ThreadingHTTPServer:
    """Create, but do not start, a read-only loopback server."""

    _require_loopback(host)

    class Handler(BaseHTTPRequestHandler):
        server_version = "DeBotNarrativeStatus/1"

        def do_GET(self) -> None:
            self._read(head=False)

        def do_HEAD(self) -> None:
            self._read(head=True)

        def do_POST(self) -> None:
            self._method_not_allowed()

        do_PUT = do_POST
        do_PATCH = do_POST
        do_DELETE = do_POST
        do_OPTIONS = do_POST
        do_TRACE = do_POST
        do_CONNECT = do_POST

        def _read(self, *, head: bool) -> None:
            if _cross_site(self):
                self._send(403, "application/json", _json({
                    "ok": False, "error": "cross-site request forbidden",
                    "read_only": True,
                }), head=head)
                return
            path = urlsplit(self.path).path
            if path == "/":
                self._send(
                    200, "text/html; charset=utf-8", DASHBOARD_HTML, head=head
                )
                return
            if path == "/api/status":
                try:
                    body = _json(dict(provider()))
                except Exception:
                    self._send(503, "application/json", _json({
                        "ok": False, "error": "status unavailable",
                        "research_only": True, "authorizes_trade": False,
                    }), head=head)
                    return
                self._send(200, "application/json", body, head=head)
                return
            self._send(404, "application/json", _json({
                "ok": False, "error": "not found", "read_only": True,
            }), head=head)

        def _method_not_allowed(self) -> None:
            self.send_response(405)
            self.send_header("Allow", "GET, HEAD")
            self._headers("application/json", len(_METHOD_BODY))
            self.end_headers()
            self.wfile.write(_METHOD_BODY)

        def _send(
            self, status: int, content_type: str, body: bytes, *, head: bool
        ) -> None:
            self.send_response(status)
            self._headers(content_type, len(body))
            self.end_headers()
            if not head:
                self.wfile.write(body)

        def _headers(self, content_type: str, length: int) -> None:
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'unsafe-inline'; "
                "style-src 'unsafe-inline'; connect-src 'self'; "
                "frame-ancestors 'none'; form-action 'none'; base-uri 'none'",
            )

        def log_message(self, _format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


create_dashboard_server = create_narrative_dashboard_server


class NarrativeDashboard:
    """Small lifecycle wrapper used by a runtime or a local operator."""

    def __init__(
        self,
        provider: StatusProvider = status_snapshot,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        self.server = create_narrative_dashboard_server(
            provider, host=host, port=port
        )
        self.thread = Thread(
            target=self.server.serve_forever,
            name="narrative-status-dashboard",
            daemon=True,
        )

    @property
    def address(self) -> tuple[str, int]:
        host, port = self.server.server_address[:2]
        return str(host), int(port)

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        if self.thread.is_alive():
            self.thread.join(timeout=3)


def _require_loopback(host: str) -> None:
    try:
        allowed = ip_address(host).is_loopback
    except ValueError:
        allowed = host.casefold() == "localhost"
    if not allowed:
        raise ValueError("narrative dashboard must bind to loopback")


def _cross_site(handler: BaseHTTPRequestHandler) -> bool:
    if handler.headers.get("Sec-Fetch-Site", "").casefold() == "cross-site":
        return True
    origin = handler.headers.get("Origin")
    if not origin:
        return False
    parsed = urlsplit(origin)
    host, port = handler.server.server_address[:2]
    expected_port = int(port)
    try:
        origin_port = parsed.port or (80 if parsed.scheme == "http" else 443)
    except ValueError:
        return True
    return not (
        parsed.scheme == "http"
        and origin_port == expected_port
        and parsed.hostname in {str(host), "127.0.0.1", "localhost", "::1"}
    )


def _json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


_METHOD_BODY = _json({
    "ok": False,
    "error": "method not allowed",
    "read_only": True,
    "authorizes_trade": False,
})
