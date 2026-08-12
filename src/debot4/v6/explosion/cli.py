"""CLI for finite explosion-signal maintenance operations."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json

from .baseline import sample_bot_baseline
from .product_baseline import sample_product_baseline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="debot4-explosion")
    subcommands = parser.add_subparsers(dest="command", required=True)
    bot = subcommands.add_parser(
        "baseline-bot",
        help="sample one finite slice of the BOT authority network",
    )
    bot.add_argument("--state-dir", required=True)
    bot.add_argument("--egress-config", required=True)
    bot.add_argument("--location", choices=("local", "remote"), required=True)
    bot.add_argument("--max-attempts", type=int, default=3)
    bot.add_argument(
        "--scope", choices=("identities", "relationships", "all"),
        default="identities",
        help="keep fast profile polling separate from slow complete relationships",
    )
    products = subcommands.add_parser(
        "baseline-products",
        help="sample one finite slice of reviewed xAI public resources",
    )
    products.add_argument("--state-dir", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "baseline-bot":
        result = sample_bot_baseline(
            state_dir=args.state_dir,
            egress_config=args.egress_config,
            location=args.location,
            max_attempts=args.max_attempts,
            scope=args.scope,
        )
    elif args.command == "baseline-products":
        result = sample_product_baseline(state_dir=args.state_dir)
    else:
        raise AssertionError("unreachable command")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if all(item["ok"] for item in result["targets"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
