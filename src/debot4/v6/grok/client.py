"""Credential-safe Grok2API client with task-specific latency lanes."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import stat

from .models import GrokSearchAnswer
from .request import (
    DISCOVERY_SEARCH,
    FORMAT_ONLY,
    GrokRequestPolicy,
    execute_chat,
    execute_image_chat,
    execute_x_search,
)
from .response import parse_answer, parse_responses_answer
from .transport import JsonTransport, UrlLibTransport


_KEY_FILE_LIMIT = 4096
_KEY_ENV = "DEBOT4_GROK2API_KEY"
_KEY_FILE_ENV = "DEBOT4_GROK2API_KEY_FILE"
_BASE_URL_ENV = "DEBOT4_GROK2API_BASE_URL"
_MODEL_ENV = "DEBOT4_GROK2API_MODEL"
_TIMEOUT_ENV = "DEBOT4_GROK2API_TIMEOUT_SECONDS"
_IMAGE_LIMIT = 4 * 1024 * 1024
_IMAGE_MEDIA_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


@dataclass(slots=True)
class Grok2ApiClient:
    """Use fast search by default; discovery and formatting are explicit lanes."""

    api_key: str = field(repr=False)
    base_url: str = "http://127.0.0.1:8000"
    model: str = "grok-chat-fast"
    timeout_seconds: float = 90.0
    attempts: int = 1
    transport: JsonTransport | None = None

    def __post_init__(self) -> None:
        self.api_key = self.api_key.strip()
        self.base_url = self.base_url.rstrip("/")
        self.model = self.model.strip()
        if not self.api_key:
            raise ValueError("Grok2API API key is required")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("Grok2API base URL must be HTTP(S)")
        GrokRequestPolicy(self.timeout_seconds, self.attempts)
        if not self.model:
            raise ValueError("invalid Grok2API client configuration")
        if self.transport is None:
            self.transport = UrlLibTransport()

    @classmethod
    def from_env(cls, **overrides: object) -> "Grok2ApiClient":
        config = dict(overrides)
        if "api_key" not in config:
            config["api_key"] = _api_key_from_env()
        _set_env_default(config, "base_url", _BASE_URL_ENV)
        _set_env_default(config, "model", _MODEL_ENV)
        _set_env_float(config, "timeout_seconds", _TIMEOUT_ENV)
        return cls(**config)

    def search(self, prompt: str, *, instructions: str) -> GrokSearchAnswer:
        """Run the real-time lane: one web search with a 90-second default cap."""

        return self._request(
            prompt,
            instructions,
            GrokRequestPolicy(self.timeout_seconds, self.attempts),
        )

    def search_discovery(
        self, prompt: str, *, instructions: str
    ) -> GrokSearchAnswer:
        """Run one bounded, deliberately slower historical discovery search."""

        return self._request(prompt, instructions, DISCOVERY_SEARCH)

    def search_x(self, prompt: str, *, instructions: str) -> GrokSearchAnswer:
        """Search native X posts and retain direct post URLs as evidence."""

        prompt, instructions = _validate_prompt(prompt, instructions)
        if self.transport is None:
            raise RuntimeError("Grok2API transport is not configured")
        policy = GrokRequestPolicy(
            self.timeout_seconds,
            self.attempts,
            web_search=False,
        )
        payload = execute_x_search(
            self.transport,
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            prompt=prompt,
            instructions=instructions,
            policy=policy,
        )
        return parse_responses_answer(payload, self.model)

    def format_json(
        self, prompt: str, *, instructions: str
    ) -> GrokSearchAnswer:
        """Repair formatting without granting the model another web search."""

        return self._request(prompt, instructions, FORMAT_ONLY)

    def analyze_image(
        self,
        prompt: str,
        *,
        image: bytes,
        media_type: str,
        instructions: str,
    ) -> GrokSearchAnswer:
        """Analyze bounded frozen image bytes; this lane cannot search the web."""

        prompt, instructions = _validate_prompt(prompt, instructions)
        media_type = media_type.strip().casefold()
        if media_type not in _IMAGE_MEDIA_TYPES:
            raise ValueError("unsupported image media type")
        if not isinstance(image, bytes) or not 1 <= len(image) <= _IMAGE_LIMIT:
            raise ValueError("image must contain between 1 byte and 4 MiB")
        if self.transport is None:
            raise RuntimeError("Grok2API transport is not configured")
        payload = execute_image_chat(
            self.transport,
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            prompt=prompt,
            instructions=instructions,
            image=image,
            media_type=media_type,
            policy=GrokRequestPolicy(self.timeout_seconds, self.attempts, False),
        )
        return parse_answer(payload, self.model)

    def _request(
        self,
        prompt: str,
        instructions: str,
        policy: GrokRequestPolicy,
    ) -> GrokSearchAnswer:
        prompt, instructions = _validate_prompt(prompt, instructions)
        if self.transport is None:
            raise RuntimeError("Grok2API transport is not configured")
        payload = execute_chat(
            self.transport,
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            prompt=prompt,
            instructions=instructions,
            policy=policy,
        )
        return parse_answer(payload, self.model)


def _validate_prompt(prompt: str, instructions: str) -> tuple[str, str]:
    prompt = prompt.strip()
    instructions = instructions.strip()
    if not prompt or not instructions:
        raise ValueError("search prompt and instructions are required")
    return prompt, instructions


def _api_key_from_env() -> str:
    direct_key = os.environ.get(_KEY_ENV, "").strip()
    if direct_key:
        return direct_key
    key_file = os.environ.get(_KEY_FILE_ENV, "").strip()
    if not key_file:
        return ""
    try:
        with open(key_file, "rb") as handle:
            metadata = os.fstat(handle.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("Grok2API API key file must be a regular file")
            if metadata.st_size > _KEY_FILE_LIMIT:
                raise ValueError("Grok2API API key file exceeds 4096 bytes")
            raw_key = handle.read(_KEY_FILE_LIMIT)
    except ValueError:
        raise
    except OSError:
        raise ValueError("Grok2API API key file cannot be read") from None
    try:
        key = raw_key.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise ValueError("Grok2API API key file must contain UTF-8 text") from None
    if not key:
        raise ValueError("Grok2API API key file is empty")
    return key


def _set_env_default(config: dict[str, object], field_name: str, env_name: str) -> None:
    value = os.environ.get(env_name, "").strip()
    if field_name not in config and value:
        config[field_name] = value


def _set_env_float(config: dict[str, object], field_name: str, env_name: str) -> None:
    value = os.environ.get(env_name, "").strip()
    if field_name in config or not value:
        return
    try:
        config[field_name] = float(value)
    except ValueError:
        raise ValueError(f"{env_name} must be numeric") from None
