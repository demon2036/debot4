#!/usr/bin/env python3
"""Transcribe one frozen KOL-directory image as non-evidentiary Grok leads."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json
from debot4.v6.grok import Grok2ApiClient


UTC = timezone.utc
ROOT = Path(__file__).resolve().parent
SOURCE_STATUS = "https://x.com/Tintinx2021/status/1978501606682558735"
SOURCE_IMAGE = "https://pbs.twimg.com/media/G3UMuGhbAAMG4vb.jpg?name=orig"
INSTRUCTIONS = """
You are transcribing a frozen screenshot, not researching the web. Read only visible
pixels. Never guess an obscured name or invent an X handle. Return compact JSON only.
Use null for unreadable fields. Keep Chinese characters and ASCII handle spelling exact.
""".strip()
PROMPTS = {
    "rows": """
Transcribe every visible KOL row in reading order. Return {"rows": [{"position": 1,
"display_name": "...", "handle": "...", "visible_labels": ["..."]}], "uncertain":
[]}. Include @ only when it is visibly printed. Do not infer handles from names.
""".strip(),
    "crosscheck": """
Independently inspect the image at high detail. Return {"accounts": [{"display_name":
"...", "handle": "...", "confidence": "high|medium|low", "literal_fragment": "..."}],
"unreadable_fragments": []}. Record only text literally visible in the image.
""".strip(),
}


def main() -> None:
    args = _args()
    image_path = Path(args.image).resolve()
    image = image_path.read_bytes()
    client = Grok2ApiClient.from_env(timeout_seconds=args.timeout, attempts=1)
    answer = client.analyze_image(
        PROMPTS[args.mode],
        image=image,
        media_type="image/jpeg",
        instructions=INSTRUCTIONS,
    )
    write_json(ROOT / args.output, {
        "schema": "debot4.grok_kol_directory_transcription.v1",
        "generated_at": datetime.now(UTC),
        "mode": args.mode,
        "source_status_url": SOURCE_STATUS,
        "source_image_url": SOURCE_IMAGE,
        "image_bytes": len(image),
        "image_sha256": sha256(image).hexdigest(),
        "grok_is_evidence": False,
        "response_id": answer.response_id,
        "model": answer.model,
        "answer": answer.text,
        "sources": [asdict(item) for item in answer.sources],
        "usage": answer.usage,
    })


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--mode", choices=tuple(PROMPTS), default="rows")
    parser.add_argument("--output", default="grok_tintin_directory_rows.json")
    parser.add_argument("--timeout", type=float, default=170)
    args = parser.parse_args()
    if not 0 < args.timeout <= 300:
        parser.error("timeout must be in (0, 300]")
    return args


if __name__ == "__main__":
    main()
