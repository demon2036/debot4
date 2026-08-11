"""Dependency-free read-only HTTP dashboard."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from typing import Any

from .dashboard_page import page
from .dex_audit.query import audit_snapshot
from .report import ledger_snapshot


class Dashboard:
    def __init__(
        self,
        host: str,
        port: int,
        database: str | Path,
        state: Any,
        audit_database: str | Path | None = None,
    ) -> None:
        self.database = Path(database)
        self.audit_database = None if audit_database is None else Path(audit_database)
        self.state = state
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                owner._get(self)

            def log_message(self, _format: str, *args: object) -> None:
                return

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.thread = Thread(target=self.server.serve_forever, name="v6-dashboard", daemon=True)

    @property
    def address(self) -> tuple[str, int]:
        host, port = self.server.server_address[:2]
        return str(host), int(port)

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def _get(self, handler: BaseHTTPRequestHandler) -> None:
        path = handler.path.split("?", 1)[0]
        if path == "/":
            self._send(handler, 200, "text/html; charset=utf-8", page())
            return
        if path == "/healthz":
            body = json.dumps({"ok": True, "runtime": self.state.snapshot()}).encode()
            self._send(handler, 200, "application/json", body)
            return
        if path == "/api/snapshot":
            body = json.dumps(
                {
                    "runtime": self.state.snapshot(),
                    "ledger": ledger_snapshot(self.database),
                    "dex_audit": self._audit_snapshot(),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            self._send(handler, 200, "application/json", body)
            return
        if path == "/api/dex-audit":
            body = json.dumps(
                self._audit_snapshot(),
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            self._send(handler, 200, "application/json", body)
            return
        self._send(handler, 404, "text/plain; charset=utf-8", b"not found\n")

    def _audit_snapshot(self) -> dict[str, Any]:
        if self.audit_database is None:
            return {
                "available": False,
                "error": "DEX audit database is not configured",
                "summary": {},
                "rows": [],
                "attempts": [],
            }
        return audit_snapshot(self.audit_database)

    @staticmethod
    def _send(
        handler: BaseHTTPRequestHandler, status: int, content_type: str, body: bytes
    ) -> None:
        handler.send_response(status)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.end_headers()
        handler.wfile.write(body)
