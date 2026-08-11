"""Create DeBot4's private Telegram runtime config from local migration data."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import tempfile


SCHEMA = "debot4.telegram-realtime.v1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--proxy-host", default="127.0.0.1")
    parser.add_argument("--proxy-port", type=int, default=10808)
    return parser


def _private_session(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    metadata = candidate.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_mode & 0o077
        or metadata.st_size <= 0
    ):
        raise ValueError("Telegram session must be a non-empty 0600 file")
    return candidate


def _desktop_api() -> tuple[int, str]:
    try:
        from opentele.api import API
    except ImportError as exc:
        raise RuntimeError("opentele2 is required only for this migration") from exc
    return int(API.TelegramDesktop.api_id), str(API.TelegramDesktop.api_hash)


def _write_private(path: Path, document: dict[str, object]) -> None:
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.parent.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", text=True
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(document, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        target.chmod(0o600)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            Path(temporary).unlink()
        except OSError:
            pass
        raise


def main() -> int:
    args = _parser().parse_args()
    if not 1 <= args.proxy_port <= 65_535:
        raise ValueError("invalid proxy port")
    session = _private_session(args.session)
    api_id, api_hash = _desktop_api()
    _write_private(args.output, {
        "schema": SCHEMA,
        "session_path": str(session),
        "api_id": api_id,
        "api_hash": api_hash,
        "proxy": {
            "proxy_type": "socks5",
            "addr": args.proxy_host,
            "port": args.proxy_port,
            "rdns": True,
        },
    })
    print('{"ok":true,"credentials_exposed":false}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
