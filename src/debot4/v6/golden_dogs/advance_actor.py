"""Pure aggregation of reviewed pre-motion public actors."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping


def summarize_advance_actors(
    events: Iterable[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    """Group receipted event-wave associations without promoting actors to KOLs."""

    grouped: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for event in events:
        actor = event.get("actor")
        source = event.get("source")
        label = event.get("label")
        wave = event.get("wave_number")
        lead = event.get("lead_seconds")
        if not all((isinstance(actor, str), actor, isinstance(source, str), source)):
            raise ValueError("advance actor event requires actor and source")
        if not isinstance(label, str) or not label:
            raise ValueError("advance actor event requires label")
        if not isinstance(wave, int) or isinstance(wave, bool) or wave < 1:
            raise ValueError("advance actor event requires a positive wave_number")
        if not isinstance(lead, int) or isinstance(lead, bool) or lead <= 0:
            raise ValueError("advance actor event requires positive lead_seconds")
        grouped[(source, actor.casefold())].append(event)
    rows = []
    for (source, normalized), items in grouped.items():
        ordered = sorted(items, key=lambda item: (
            int(item["occurred_at"]), str(item["label"]), int(item["wave_number"])
        ))
        closest = min(items, key=lambda item: (
            int(item["lead_seconds"]), -int(item["occurred_at"]),
            str(item["label"]), int(item["wave_number"]),
        ))
        waves = {(str(item["label"]), int(item["wave_number"])) for item in items}
        fresh_waves = {
            (str(item["label"]), int(item["wave_number"])) for item in items
            if item.get("freshness") == "fresh_pre_motion"
        }
        rows.append({
            "source": source, "actor": str(ordered[0]["actor"]),
            "normalized_actor": normalized,
            "advance_event_count": len(items), "advance_wave_count": len(waves),
            "target_count": len({label for label, _ in waves}),
            "fresh_advance_wave_count": len(fresh_waves),
            "closest_lead_seconds": int(closest["lead_seconds"]),
            "closest_event": closest,
            "events": tuple(ordered),
            "qualification_status": "discovery_lead_only",
        })
    return tuple(sorted(rows, key=lambda row: (
        -int(row["advance_wave_count"]), int(row["closest_lead_seconds"]),
        str(row["normalized_actor"]),
    )))
