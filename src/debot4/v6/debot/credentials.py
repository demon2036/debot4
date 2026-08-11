"""Private, validated DeBot cookie credentials independent of browsers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
import tempfile


SCHEMA = "debot4.debot-cookies.v1"
MAX_FILE_BYTES = 128 * 1024
_ROOT_FIELDS = frozenset({"schema", "cookies"})
_COOKIE_FIELDS = frozenset({"name", "value", "domain", "path"})


class DeBotCredentialError(RuntimeError):
    """Private DeBot credentials are absent, unsafe, or malformed."""


@dataclass(frozen=True, slots=True)
class DeBotCookie:
    name: str
    value: str
    domain: str
    path: str = "/"

    def __post_init__(self) -> None:
        name = _text(self.name, "cookie name", 256)
        value = _text(self.value, "cookie value", 16_384, allow_empty=True)
        domain = _text(self.domain, "cookie domain", 253).casefold()
        path = _text(self.path, "cookie path", 2_048)
        if domain != "debot.ai" and not domain.endswith(".debot.ai"):
            raise DeBotCredentialError("cookie domain is outside debot.ai")
        if not path.startswith("/"):
            raise DeBotCredentialError("cookie path must start with slash")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "path", path)


def load_debot_cookies(path: str | Path) -> tuple[DeBotCookie, ...]:
    """Read an owner-private credential file and reject ambiguous structure."""

    credential = Path(path).expanduser().resolve()
    try:
        metadata = credential.stat()
    except OSError as exc:
        raise DeBotCredentialError("DeBot credential file is unavailable") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise DeBotCredentialError("DeBot credential path is not a regular file")
    if metadata.st_mode & 0o077:
        raise DeBotCredentialError("DeBot credential file must have mode 0600")
    if not 0 < metadata.st_size <= MAX_FILE_BYTES:
        raise DeBotCredentialError("DeBot credential file size is invalid")
    try:
        document = json.loads(credential.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeBotCredentialError("DeBot credential file is invalid JSON") from exc
    if not isinstance(document, dict) or set(document) != _ROOT_FIELDS:
        raise DeBotCredentialError("DeBot credential schema is invalid")
    if document.get("schema") != SCHEMA:
        raise DeBotCredentialError("DeBot credential schema is unsupported")
    raw = document.get("cookies")
    if not isinstance(raw, list) or not 1 <= len(raw) <= 256:
        raise DeBotCredentialError("DeBot credential cookie list is invalid")
    cookies = tuple(_cookie(item) for item in raw)
    identities = {(item.name, item.domain, item.path) for item in cookies}
    if len(identities) != len(cookies):
        raise DeBotCredentialError("DeBot credential contains duplicate cookies")
    return cookies


def save_debot_cookies(
    path: str | Path, cookies: Iterable[DeBotCookie | Mapping[str, object]],
) -> None:
    """Atomically persist only fields needed by the direct DeBot API client."""

    destination = Path(path).expanduser().resolve()
    parsed = tuple(
        item if isinstance(item, DeBotCookie) else _cookie(item)
        for item in cookies
    )
    if not parsed:
        raise DeBotCredentialError("cannot save an empty DeBot credential")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.parent.chmod(0o700)
    payload = json.dumps(
        {
            "schema": SCHEMA,
            "cookies": [
                {
                    "name": item.name,
                    "value": item.value,
                    "domain": item.domain,
                    "path": item.path,
                }
                for item in parsed
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent,
            prefix=f".{destination.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            temporary.chmod(0o600)
            stream.write(payload + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        destination.chmod(0o600)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _cookie(value: object) -> DeBotCookie:
    if not isinstance(value, Mapping):
        raise DeBotCredentialError("DeBot cookie must be an object")
    required = {"name", "value", "domain", "path"}
    if not required.issubset(value) or not set(value).issubset(
        _COOKIE_FIELDS | {"secure", "http_only"}
    ):
        raise DeBotCredentialError("DeBot cookie fields are invalid")
    return DeBotCookie(
        name=value["name"], value=value["value"],
        domain=value["domain"], path=value["path"],
    )


def _text(
    value: object, name: str, limit: int, *, allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise DeBotCredentialError(f"{name} must be text")
    if value != value.strip() or len(value) > limit or (not value and not allow_empty):
        raise DeBotCredentialError(f"{name} is invalid")
    return value
