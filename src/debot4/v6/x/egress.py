"""Validated round-robin SOCKS5 egress for browser-free X requests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from threading import Lock
from typing import Callable, Protocol
import tomllib
import urllib.error
import urllib.parse
import urllib.request

import requests


_NODE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,31}")
_RETRYABLE_HTTP = frozenset({403, 408, 425, 429, 500, 502, 503, 504})


class FxEgressError(RuntimeError):
    """All bounded egress attempts failed without exposing proxy details."""


class RequestOpener(Protocol):
    def open(
        self, request: urllib.request.Request, *, timeout: float
    ) -> object: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


@dataclass(frozen=True, slots=True)
class FxEgressNode:
    node_id: str
    proxy_host: str
    proxy_port: int

    def __post_init__(self) -> None:
        node_id = self.node_id.strip().casefold()
        host = self.proxy_host.strip()
        if not _NODE_ID.fullmatch(node_id) or not host:
            raise ValueError("egress node requires a valid ID and host")
        if isinstance(self.proxy_port, bool) or not 1 <= self.proxy_port <= 65_535:
            raise ValueError("egress proxy port is invalid")
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "proxy_host", host)


@dataclass(slots=True)
class _NodeRuntime:
    node: FxEgressNode
    opener: RequestOpener
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    last_error_type: str | None = None


class _RequestsResponse:
    """Small urllib-compatible view over a streamed requests response."""

    def __init__(self, response: requests.Response) -> None:
        self._response = response
        self.status = response.status_code
        self.headers = response.headers

    def __enter__(self) -> "_RequestsResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def geturl(self) -> str:
        return self._response.url

    def read(self, size: int = -1) -> bytes:
        amount = None if size < 0 else size
        return self._response.raw.read(amount, decode_content=True)

    def close(self) -> None:
        self._response.close()


class _RequestsSocksOpener:
    def __init__(self, node: FxEgressNode) -> None:
        host = f"[{node.proxy_host}]" if ":" in node.proxy_host else node.proxy_host
        proxy = f"socks5h://{host}:{node.proxy_port}"
        self._proxies = {"http": proxy, "https": proxy}
        self._session = requests.Session()
        self._session.trust_env = False

    def open(
        self, request: urllib.request.Request, *, timeout: float
    ) -> _RequestsResponse:
        try:
            response = self._session.request(
                request.get_method(),
                request.full_url,
                headers=dict(request.header_items()),
                data=request.data,
                timeout=timeout,
                allow_redirects=False,
                stream=True,
                proxies=self._proxies,
            )
        except requests.RequestException as exc:
            raise urllib.error.URLError("SOCKS request failed") from exc
        response.raw.decode_content = True
        return _RequestsResponse(response)

    def close(self) -> None:
        self._session.close()


class FxEgressPool:
    """Thread-safe round-robin routing with bounded node failover."""

    def __init__(
        self,
        nodes: tuple[FxEgressNode, ...],
        *,
        max_attempts: int = 3,
        opener_factory: Callable[[FxEgressNode], RequestOpener] | None = None,
    ) -> None:
        if not nodes or len(nodes) > 64:
            raise ValueError("egress pool requires between 1 and 64 nodes")
        if isinstance(max_attempts, bool) or not 1 <= max_attempts <= len(nodes):
            raise ValueError("egress attempts must fit the configured node count")
        identifiers = [node.node_id for node in nodes]
        endpoints = [(node.proxy_host, node.proxy_port) for node in nodes]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("egress node IDs must be unique")
        if len(endpoints) != len(set(endpoints)):
            raise ValueError("egress proxy endpoints must be unique")
        factory = opener_factory or _socks_opener
        self._nodes = tuple(_NodeRuntime(node, factory(node)) for node in nodes)
        self.max_attempts = max_attempts
        self._cursor = 0
        self._lock = Lock()

    @classmethod
    def from_toml(
        cls,
        path: str | Path,
        *,
        location: str = "local",
        max_attempts: int = 3,
        opener_factory: Callable[[FxEgressNode], RequestOpener] | None = None,
    ) -> "FxEgressPool":
        selected = location.strip().casefold()
        if selected not in {"local", "remote"}:
            raise ValueError("egress location must be local or remote")
        source = Path(path).expanduser().resolve()
        try:
            raw = source.read_bytes()
        except OSError:
            raise ValueError("egress pool configuration is unavailable") from None
        if not 1 <= len(raw) <= 128 * 1024:
            raise ValueError("egress pool configuration size is invalid")
        try:
            document = tomllib.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError):
            raise ValueError("egress pool configuration is invalid") from None
        if document.get("schema") != "debot4.egress_pool.v1":
            raise ValueError("egress pool schema is unsupported")
        rows = document.get("nodes")
        if not isinstance(rows, list):
            raise ValueError("egress pool nodes are missing")
        nodes = tuple(_parse_node(row, selected) for row in rows)
        return cls(
            nodes, max_attempts=max_attempts, opener_factory=opener_factory
        )

    def open(
        self, request: urllib.request.Request, *, timeout: float
    ) -> object:
        runtimes = self._route()
        last_error: BaseException | None = None
        for runtime in runtimes:
            self._mark_attempt(runtime)
            try:
                response = runtime.opener.open(request, timeout=timeout)
            except urllib.error.HTTPError as exc:
                if exc.code not in _RETRYABLE_HTTP:
                    self._mark_success(runtime)
                    raise
                exc.close()
                last_error = exc
                self._mark_failure(runtime, exc)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                self._mark_failure(runtime, exc)
            else:
                status = getattr(response, "status", None)
                if status in _RETRYABLE_HTTP:
                    close = getattr(response, "close", None)
                    if callable(close):
                        close()
                    error = urllib.error.HTTPError(
                        request.full_url, int(status), "retryable response", {}, None
                    )
                    last_error = error
                    self._mark_failure(runtime, error)
                    continue
                self._mark_success(runtime)
                return response
        raise FxEgressError("all configured X egress attempts failed") from last_error

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "available": True,
                "strategy": "round_robin_bounded_failover",
                "configured_nodes": len(self._nodes),
                "max_attempts": self.max_attempts,
                "nodes": [
                    {
                        "id": runtime.node.node_id,
                        "attempts": runtime.attempts,
                        "successes": runtime.successes,
                        "failures": runtime.failures,
                        "last_error_type": runtime.last_error_type,
                    }
                    for runtime in self._nodes
                ],
            }

    def close(self) -> None:
        for runtime in self._nodes:
            close = getattr(runtime.opener, "close", None)
            if callable(close):
                close()

    def _route(self) -> tuple[_NodeRuntime, ...]:
        with self._lock:
            start = self._cursor
            self._cursor = (self._cursor + 1) % len(self._nodes)
        return tuple(
            self._nodes[(start + offset) % len(self._nodes)]
            for offset in range(self.max_attempts)
        )

    def _mark_attempt(self, runtime: _NodeRuntime) -> None:
        with self._lock:
            runtime.attempts += 1

    def _mark_success(self, runtime: _NodeRuntime) -> None:
        with self._lock:
            runtime.successes += 1
            runtime.last_error_type = None

    def _mark_failure(
        self, runtime: _NodeRuntime, error: BaseException
    ) -> None:
        with self._lock:
            runtime.failures += 1
            runtime.last_error_type = type(error).__name__


def direct_opener() -> RequestOpener:
    return urllib.request.build_opener(_NoRedirect())


def _socks_opener(node: FxEgressNode) -> RequestOpener:
    return _RequestsSocksOpener(node)


def _parse_node(value: object, location: str) -> FxEgressNode:
    if not isinstance(value, dict):
        raise ValueError("egress pool node is invalid")
    node_id = str(value.get("id") or "")
    endpoint = str(value.get(f"{location}_url") or "")
    try:
        parsed = urllib.parse.urlsplit(endpoint)
        port = parsed.port
    except ValueError:
        raise ValueError("egress proxy URL is invalid") from None
    if (
        parsed.scheme.casefold() != "socks5h"
        or not parsed.hostname
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("egress proxy URL is invalid")
    return FxEgressNode(node_id, parsed.hostname, port)
