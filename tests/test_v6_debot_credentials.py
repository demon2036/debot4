from __future__ import annotations

import json
from pathlib import Path
import stat

import pytest

from debot4.v6.debot.credentials import (
    DeBotCookie,
    DeBotCredentialError,
    SCHEMA,
    load_debot_cookies,
    save_debot_cookies,
)


def test_private_cookie_file_round_trips_without_browser_state(tmp_path: Path) -> None:
    path = tmp_path / "private" / "debot.json"
    expected = (
        DeBotCookie("session", "secret", ".debot.ai", "/"),
        DeBotCookie("clearance", "token", "app.debot.ai", "/api"),
    )

    save_debot_cookies(path, expected)

    assert load_debot_cookies(path) == expected
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["schema"] == SCHEMA
    assert set(document) == {"schema", "cookies"}


def test_loader_rejects_world_readable_or_cross_domain_credentials(
    tmp_path: Path,
) -> None:
    path = tmp_path / "debot.json"
    save_debot_cookies(path, (
        DeBotCookie("session", "secret", ".debot.ai", "/"),
    ))
    path.chmod(0o644)
    with pytest.raises(DeBotCredentialError, match="0600"):
        load_debot_cookies(path)

    path.write_text(json.dumps({
        "schema": SCHEMA,
        "cookies": [{
            "name": "session", "value": "secret",
            "domain": ".example.com", "path": "/",
        }],
    }), encoding="utf-8")
    path.chmod(0o600)
    with pytest.raises(DeBotCredentialError, match="outside"):
        load_debot_cookies(path)


def test_loader_rejects_unknown_fields_and_duplicate_cookie_identity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "debot.json"
    document = {
        "schema": SCHEMA,
        "cookies": [
            {"name": "a", "value": "1", "domain": ".debot.ai", "path": "/"},
            {"name": "a", "value": "2", "domain": ".debot.ai", "path": "/"},
        ],
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)
    with pytest.raises(DeBotCredentialError, match="duplicate"):
        load_debot_cookies(path)

    document["unexpected"] = True
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(DeBotCredentialError, match="schema"):
        load_debot_cookies(path)
