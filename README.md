# DeBot4

DeBot4 is an evidence-first meme narrative radar. The current production path is
the independent `v6 narrative` service: it collects fast signals from several
sources, investigates why a narrative is moving, verifies exact public evidence,
and persists an auditable research package.

It is currently **research-only**. The running narrative service cannot place a
real-money order, does not publish a target-price guess, and does not claim
profitability.

## Architecture

```text
external sources
├── X / FxTwitter timelines
├── Telegram public pages and optional personal-session realtime feed
├── DeBot KOL and Smart Money signals
└── exact-CA BSC 1h market movers
    └── concurrent collectors
        ├── identity checks and source checkpoints
        ├── durable priority queue (SQLite)
        └── Grok narrative worker
            ├── active research: a monitored actor publishes
            ├── passive research: DeBot or the market moves first
            ├── exact X-status verification
            ├── exact-CA evidence binding
            └── immutable research packages
                └── read-only local dashboard
```

The actor registry records stable X identities, role, tier, region, language,
ecosystem, authority boundary, evidence URLs, and polling priority. The catalog
includes global agenda accounts, ecosystem authorities, domain experts, and
propagation KOLs across BSC, Solana, Robinhood, Ethereum, Base, China, Korea,
Japan, and global English-language communities.

## What the runtime does

- Polls high-impact X accounts every 5–15 seconds according to reviewed tier.
- Preserves original posts, replies, quotes, articles, cards, and polls.
- Runs DeBot, X, Telegram, market, and research loops independently so a slow
  model request does not stop collection.
- Polls the DeBot source at a configurable 0.25–5 second cadence.
- Polls an exact-CA BSC 1h mover board at a configurable 0.5–15 second cadence.
- Prioritizes fresh high-authority events over historical replay work.
- Uses Grok to investigate origin, why-now, propagation path, competing CAs,
  narrative and market leaders, phase, counter-evidence, and invalidation.
- Treats model output as a lead, not evidence: returned status URLs must be
  fetched and identity-verified before they can support a finding.
- Fails closed to `WAIT` when the narrative or exact contract binding is not
  sufficiently supported.
- Exposes source health, actor coverage, queue state, recent research, and
  optional repost-canary observations through a loopback-only dashboard.

## Quick start

Python 3.12 or newer is required.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[telegram]'
```

Collect once without requiring Grok:

```bash
python -m debot4.v6.narrative.cli collect-once
```

Research one queued item:

```bash
python -m debot4.v6.narrative.cli work-once
```

Run collectors and research continuously:

```bash
python -m debot4.v6.narrative.cli run
```

Run the service with its local dashboard:

```bash
python -m debot4.v6.narrative.serve --host 127.0.0.1 --port 8777
```

Then open `http://127.0.0.1:8777/` on the same machine.

## Credentials and local state

Credentials are loaded from environment-owned files or environment variables.
They must never be committed. Runtime databases, checkpoints, logs, cookies,
API keys, and authenticated Telegram sessions are ignored by Git.

Common settings include:

```text
DEBOT4_NARRATIVE_STATE_DIR
DEBOT4_DEBOT_COOKIE_FILE
DEBOT4_GROK2API_KEY
DEBOT4_GROK2API_KEY_FILE
DEBOT4_GROK2API_BASE_URL
DEBOT4_TELEGRAM_REALTIME_CONFIG
```

## Safety boundary

```text
research result
├── may describe a narrative and verified evidence
├── may return WAIT when evidence is incomplete
├── cannot authorize a trade
├── cannot submit an order
└── cannot claim the strategy is profitable
```

The repository also contains isolated experimental ledger, valuation, market,
and entry-boundary modules. They are not wired into the running narrative
service and must not be presented as live execution capability.

## Verification

```bash
pytest -q
find . -type f -name '*.py' -not -path './.venv/*' -print0 \
  | xargs -0 -n1 sh -c 'n=$(wc -l < "$0"); [ "$n" -le 300 ] || echo "$n $0"'
```

Every Python source and test file is required to stay at or below 300 physical
lines. Engineering rules and contribution constraints are documented in
[`AGENTS.md`](AGENTS.md).
