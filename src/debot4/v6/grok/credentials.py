"""Shared bounded loading for model API credentials."""

from __future__ import annotations

from collections.abc import Mapping
import os
import stat


KEY_FILE_LIMIT = 4_096


def api_key_from_env(
    environ: Mapping[str, str],
    *,
    key_env: str,
    key_file_env: str,
    label: str,
) -> str:
    direct_key = environ.get(key_env, "").strip()
    if direct_key:
        return direct_key
    key_file = environ.get(key_file_env, "").strip()
    if not key_file:
        return ""
    try:
        with open(key_file, "rb") as handle:
            metadata = os.fstat(handle.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError(f"{label} API key file must be a regular file")
            if metadata.st_size > KEY_FILE_LIMIT:
                raise ValueError(f"{label} API key file exceeds 4096 bytes")
            raw_key = handle.read(KEY_FILE_LIMIT)
    except ValueError:
        raise
    except OSError:
        raise ValueError(f"{label} API key file cannot be read") from None
    try:
        key = raw_key.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise ValueError(
            f"{label} API key file must contain UTF-8 text"
        ) from None
    if not key:
        raise ValueError(f"{label} API key file is empty")
    return key


__all__ = ["KEY_FILE_LIMIT", "api_key_from_env"]
