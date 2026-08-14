"""Bounded, restart-safe two-sided state for catalyst-to-mint joins."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
from threading import RLock
import tempfile

from ..debot.ranks_models import RANK_STAGES, RankSnapshot
from ..identity import utc_datetime, utc_now
from ..x.models import XPost
from .catalyst_mint import CatalystMintMatch, x_status_ids
from .catalyst_mint_state_codec import (
    decode_mint,
    decode_post,
    encode_mint,
    encode_post,
)


STATE_SCHEMA = "debot4.v6.catalyst-mint-state.v1"
_STAGE_ORDER = {stage: index for index, stage in enumerate(RANK_STAGES)}


class CatalystMintStateError(ValueError):
    """Persistent join state is malformed or internally inconsistent."""


class CatalystMintState:
    """Persist both arrival orders and emit only exact, unacknowledged matches."""

    def __init__(
        self,
        path: str | Path,
        *,
        clock: Callable[[], datetime] = utc_now,
        retention_seconds: float = 900,
        max_posts: int = 512,
        max_mints: int = 2_000,
        max_emitted: int = 4_096,
    ) -> None:
        if not 600 <= float(retention_seconds) <= 3_600:
            raise ValueError("catalyst mint retention must be between 600 and 3600 seconds")
        if not 1 <= max_posts <= 10_000 or not 1 <= max_mints <= 20_000:
            raise ValueError("catalyst mint observation limits are invalid")
        if not 1 <= max_emitted <= 100_000:
            raise ValueError("catalyst mint emitted limit is invalid")
        self.path = Path(path)
        self.clock = clock
        self.retention = timedelta(seconds=float(retention_seconds))
        self.max_posts = max_posts
        self.max_mints = max_mints
        self.max_emitted = max_emitted
        self._lock = RLock()
        self._secure_parent()
        self._posts, self._mints, self._emitted = self._read()

    def observe_posts(
        self, posts: Iterable[XPost],
    ) -> tuple[CatalystMintMatch, ...]:
        with self._lock:
            changed = False
            for post in posts:
                changed = self._merge_post(post) or changed
            changed = self._prune(self._now()) or changed
            if changed:
                self._write()
            return self._pending()

    def observe_mints(
        self, snapshots: Iterable[RankSnapshot],
    ) -> tuple[CatalystMintMatch, ...]:
        with self._lock:
            changed = False
            for snapshot in snapshots:
                if snapshot.created_at is None or not x_status_ids(snapshot.social_urls):
                    continue
                changed = self._merge_mint(snapshot) or changed
            changed = self._prune(self._now()) or changed
            if changed:
                self._write()
            return self._pending()

    def acknowledge(self, match_ids: Iterable[str]) -> None:
        with self._lock:
            changed = False
            for raw in match_ids:
                value = str(raw).strip()
                if not value.startswith("catalyst-mint-") or len(value) > 128:
                    raise ValueError("invalid catalyst mint match ID")
                if value not in self._emitted:
                    self._emitted[value] = None
                    changed = True
            while len(self._emitted) > self.max_emitted:
                self._emitted.pop(next(iter(self._emitted)))
                changed = True
            if changed:
                self._write()

    def _merge_post(self, post: XPost) -> bool:
        old = self._posts.get(post.tweet_id)
        if old is None:
            self._posts[post.tweet_id] = post
            return True
        if _post_content(old) != _post_content(post):
            raise CatalystMintStateError("one X status ID has conflicting content")
        if post.fetched_at < old.fetched_at:
            self._posts[post.tweet_id] = replace(old, fetched_at=post.fetched_at)
            return True
        return False

    def _merge_mint(self, item: RankSnapshot) -> bool:
        old = self._mints.get(item.token_address)
        if old is None:
            self._mints[item.token_address] = item
            return True
        if old.created_at != item.created_at:
            raise CatalystMintStateError("one token has conflicting creation times")
        social_urls = tuple(dict.fromkeys((*old.social_urls, *item.social_urls)))
        social_enriched = social_urls != old.social_urls
        stage = max((old.stage, item.stage), key=_STAGE_ORDER.__getitem__)
        merged = replace(
            old,
            stage=stage,
            fetched_at=(
                item.fetched_at
                if social_enriched
                else min(old.fetched_at, item.fetched_at)
            ),
            name=old.name or item.name,
            symbol=old.symbol or item.symbol,
            provider_fdv_usd=old.provider_fdv_usd or item.provider_fdv_usd,
            launchpad=old.launchpad or item.launchpad,
            description=old.description or item.description,
            social_urls=social_urls,
            launched=old.launched or item.launched,
        )
        if merged != old:
            self._mints[item.token_address] = merged
            return True
        return False

    def _pending(self) -> tuple[CatalystMintMatch, ...]:
        matches: dict[str, CatalystMintMatch] = {}
        for mint in self._mints.values():
            for status_id in x_status_ids(mint.social_urls):
                post = self._posts.get(status_id)
                if post is None:
                    continue
                match = CatalystMintMatch.from_observations(post, mint)
                if match is not None and match.match_id not in self._emitted:
                    matches[match.match_id] = match
        return tuple(sorted(
            matches.values(),
            key=lambda item: (item.observed_at, item.exact_ca, item.catalyst_tweet_id),
        ))

    def _prune(self, now: datetime) -> bool:
        cutoff = now - self.retention
        posts = {
            key: value for key, value in self._posts.items()
            if utc_datetime(value.created_at) >= cutoff
        }
        mints = {
            key: value for key, value in self._mints.items()
            if value.created_at is not None and utc_datetime(value.created_at) >= cutoff
        }
        posts = dict(sorted(
            posts.items(), key=lambda item: item[1].created_at, reverse=True,
        )[: self.max_posts])
        mints = dict(sorted(
            mints.items(), key=lambda item: item[1].created_at, reverse=True,
        )[: self.max_mints])
        changed = posts != self._posts or mints != self._mints
        self._posts, self._mints = posts, mints
        return changed

    def _read(self) -> tuple[dict[str, XPost], dict[str, RankSnapshot], dict[str, None]]:
        if not self.path.exists():
            return {}, {}, {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CatalystMintStateError("cannot read catalyst mint state") from exc
        if not isinstance(raw, dict) or set(raw) != {"schema", "posts", "mints", "emitted"}:
            raise CatalystMintStateError("invalid catalyst mint state structure")
        if raw.get("schema") != STATE_SCHEMA:
            raise CatalystMintStateError("unsupported catalyst mint state schema")
        posts, mints, emitted = raw["posts"], raw["mints"], raw["emitted"]
        if not isinstance(posts, list) or not isinstance(mints, list) or not isinstance(emitted, list):
            raise CatalystMintStateError("invalid catalyst mint state collections")
        if len(posts) > self.max_posts or len(mints) > self.max_mints or len(emitted) > self.max_emitted:
            raise CatalystMintStateError("catalyst mint state exceeds configured bounds")
        try:
            decoded_posts = [decode_post(item) for item in posts]
            decoded_mints = [decode_mint(item) for item in mints]
            emitted_ids = [str(item) for item in emitted]
        except (KeyError, TypeError, ValueError) as exc:
            raise CatalystMintStateError("invalid catalyst mint state value") from exc
        if len({item.tweet_id for item in decoded_posts}) != len(decoded_posts):
            raise CatalystMintStateError("duplicate catalyst post in state")
        if len({item.token_address for item in decoded_mints}) != len(decoded_mints):
            raise CatalystMintStateError("duplicate catalyst mint in state")
        return (
            {item.tweet_id: item for item in decoded_posts},
            {item.token_address: item for item in decoded_mints},
            dict.fromkeys(emitted_ids),
        )

    def _write(self) -> None:
        self._secure_parent()
        document = json.dumps({
            "schema": STATE_SCHEMA,
            "posts": [encode_post(item) for item in self._posts.values()],
            "mints": [encode_mint(item) for item in self._mints.values()],
            "emitted": list(self._emitted),
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.path.parent,
                prefix=f".{self.path.name}.", suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                temporary.chmod(0o600)
                stream.write(document + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self.path.chmod(0o600)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def _secure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        if self.path.exists() and (self.path.is_symlink() or not self.path.is_file()):
            raise CatalystMintStateError("catalyst mint state must be a regular file")
        if self.path.exists():
            self.path.chmod(0o600)

    def _now(self) -> datetime:
        return utc_datetime(self.clock())


def _post_content(value: XPost) -> tuple[object, ...]:
    return (
        value.author, value.text, value.created_at, value.post_type,
        value.target_author, value.target_text, value.urls, value.bsc_contracts,
    )
