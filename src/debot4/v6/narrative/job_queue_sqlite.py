"""Small SQLite safety helpers for the narrative job queue."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import ContextManager


def prepare_private_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("narrative job database must be a regular file")
    if not path.exists():
        flags = os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
        os.close(descriptor)
    path.chmod(0o600)


def secure_sqlite_files(path: Path) -> None:
    for item in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        if item.is_file():
            item.chmod(0o600)


@contextmanager
def immediate_transaction(
    connection: sqlite3.Connection,
    lock: ContextManager[object],
    after: Callable[[], None],
) -> Iterator[sqlite3.Connection]:
    with lock:
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            after()
