"""Small restart-safe state for detecting DeBot rank KOL increases."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from .ranks_models import RankKolIncrease, RankSnapshot


UTC = timezone.utc


class RankState:
    def __init__(self, path: str | Path, *, max_tokens: int = 1_000) -> None:
        self.path = Path(path)
        self.max_tokens = max_tokens
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._tokens = self._load()

    def observe(self, snapshot: RankSnapshot) -> RankKolIncrease | None:
        old = self._tokens.get(snapshot.token_address)
        change = None
        if old is not None and snapshot.kols > int(old["kols"]):
            change = RankKolIncrease(
                snapshot=snapshot,
                previous_kols=int(old["kols"]),
                previous_aliases=tuple(old.get("aliases") or ()),
            )
        self._tokens[snapshot.token_address] = {
            "kols": snapshot.kols,
            "aliases": list(snapshot.kol_aliases),
            "stage": snapshot.stage,
            "seen_at": snapshot.fetched_at.isoformat(),
        }
        return change

    def save(self) -> None:
        ranked = sorted(
            self._tokens.items(),
            key=lambda item: str(item[1].get("seen_at") or ""),
            reverse=True,
        )[: self.max_tokens]
        self._tokens = dict(ranked)
        payload = json.dumps(
            {"schema": "debot_rank_state.v1", "tokens": self._tokens},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, self.path)

    def _load(self) -> dict[str, dict[str, object]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        if raw.get("schema") != "debot_rank_state.v1":
            return {}
        tokens = raw.get("tokens")
        if not isinstance(tokens, dict):
            return {}
        output: dict[str, dict[str, object]] = {}
        for address, item in list(tokens.items())[: self.max_tokens]:
            if not isinstance(item, dict):
                continue
            try:
                datetime.fromisoformat(str(item.get("seen_at"))).astimezone(UTC)
                count = int(item.get("kols"))
            except (TypeError, ValueError):
                continue
            if count >= 0:
                output[str(address)] = dict(item)
        return output
