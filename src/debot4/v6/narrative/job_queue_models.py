"""Lifecycle values for the narrative-only durable queue."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Any

from ..identity import utc_datetime
from .job_payloads import NarrativeJobInput, decode_job_input, encode_job_input


_WORKER = re.compile(r"[A-Za-z0-9_.:@-]{1,128}")
_LEASE = re.compile(r"[0-9a-f]{32}")
_ERROR_TYPE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]{0,127}")


class JobStatus(str, Enum):
    PENDING = "pending"
    LEASED = "leased"
    DONE = "done"
    FAILED = "failed"


class LeaseLostError(RuntimeError):
    """The caller no longer owns a live lease for the requested job."""


class JobContentConflict(RuntimeError):
    """A content ID unexpectedly names different canonical bytes."""


@dataclass(frozen=True, slots=True)
class NarrativeJob:
    job_id: str
    kind: str
    payload: NarrativeJobInput
    status: JobStatus
    attempts: int
    max_attempts: int
    priority: int
    available_at: datetime
    created_at: datetime
    updated_at: datetime
    lease_owner: str | None = None
    lease_id: str | None = None
    lease_expires_at: datetime | None = None
    error_type: str | None = None
    completed_at: datetime | None = None


def worker_identity(value: object) -> str:
    worker = str(value).strip()
    if not _WORKER.fullmatch(worker):
        raise ValueError("invalid narrative worker identity")
    return worker


def lease_identity(value: object) -> str:
    lease_id = str(value).strip()
    if not _LEASE.fullmatch(lease_id):
        raise ValueError("invalid narrative lease identity")
    return lease_id


def sanitized_error_type(error: BaseException | type[BaseException]) -> str:
    if isinstance(error, type) and issubclass(error, BaseException):
        name = error.__name__
    elif isinstance(error, BaseException):
        name = type(error).__name__
    else:
        raise TypeError("error must be an exception or exception type")
    return name if _ERROR_TYPE.fullmatch(name) else "Exception"


def stored_time(value: object) -> datetime:
    return utc_datetime(datetime.fromisoformat(str(value)))


def optional_time(value: object) -> datetime | None:
    return None if value is None else stored_time(value)


def job_from_row(row: Any) -> NarrativeJob:
    kind, payload = decode_job_input(row["payload_json"])
    expected_id, expected_kind, content_sha256, document = encode_job_input(payload)
    if (
        kind != row["kind"]
        or expected_kind != kind
        or expected_id != row["job_id"]
        or content_sha256 != row["content_sha256"]
        or document != row["payload_json"]
    ):
        raise JobContentConflict(row["job_id"])
    return NarrativeJob(
        job_id=row["job_id"],
        kind=kind,
        payload=payload,
        status=JobStatus(row["status"]),
        attempts=int(row["attempts"]),
        max_attempts=int(row["max_attempts"]),
        priority=int(row["priority"]),
        available_at=stored_time(row["available_at"]),
        created_at=stored_time(row["created_at"]),
        updated_at=stored_time(row["updated_at"]),
        lease_owner=row["lease_owner"],
        lease_id=row["lease_id"],
        lease_expires_at=optional_time(row["lease_expires_at"]),
        error_type=row["error_type"],
        completed_at=optional_time(row["completed_at"]),
    )
