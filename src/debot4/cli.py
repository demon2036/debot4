"""Narrative-only DeBot4 command entry point."""

from __future__ import annotations

from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    from .v6.narrative.cli import main as narrative_main

    return narrative_main(argv)
