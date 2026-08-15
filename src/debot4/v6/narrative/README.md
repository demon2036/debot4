# v6 narrative boundary

This package owns the independent X-to-mint alert and narrative-research
runtime. Adapters collect facts; pure domain rules decide; persistence keeps
evidence and delivery state; the service only orchestrates those boundaries.

## Mint-alert critical path

```text
reviewed X account publishes
├── preserve exact status ID, author, text, created_at, fetched_at
└── bind matching DeBot metadata by exact status URL and exact CA
    ├── new
    ├── completing
    └── completed
        └── 1.5-second ambiguity stabilization
            ├── multiple exact CAs for one post -> REJECT
            └── one exact candidate -> tool-free gpt-5.3-codex-spark
                ├── A before 15s -> durable alert outbox
                └── R/error/late response -> REJECT
```

The three DeBot stages rotate at the configured mint polling cadence. With the
default 0.5-second cadence, a complete stage cycle is 1.5 seconds. Preparing
tokens may predate the X post; the alert deadline is measured from the X post's
own creation time. One X post resolving to multiple exact CAs is rejected; a
later conflicting CA is retained as an audit violation.

Spark receives only the exact X post and the matched DeBot token metadata. It
runs without search or tools, with one bounded request, and must explicitly
approve exceptional meme, cultural, or current-attention potential. Missing
credentials, ambiguity, model errors, and timeouts fail closed. The alert is
stored before narrative research is queued; delivery retries from the durable
outbox, and the JSONL sink flushes each event immediately. RPC remains outside
this path. Optional BSC zero-address log collection is off by default, records
raw location evidence only, and can never trigger an alert.

## Research path

```text
X / Telegram / DeBot / market observation
└── bounded priority queue
    └── exact-source research
        ├── origin and why-now
        ├── propagation and competing CAs
        ├── counter-evidence and invalidation
        └── immutable research package
```

Research is asynchronous and never authorizes a trade. Its model output is a
lead until its source URL and identity are independently verified. The separate
bounded Spark classifier is the required semantic approval for mint alerts, but
it does not authorize a trade.

## Ten-minute audit

`python -m debot4.v6.narrative.audit_mint_alerts` fetches the exact CoinMarketCap
BSC one-hour gainer board, then reads the gate, alert outbox, and only the DeBot
mint rows for those exact CAs in SQLite read-only mode. A separate aggregate
count preserves overall DeBot coverage without loading the full observation set.

Hard violations include a selected gate match missing from the outbox, a recent
orphan alert, an alert attached to a rejected group, an alert without matching
Spark approval, unresolved state beyond the SLA, and detection or delivery after
15 seconds. Of the quality-qualified market leaders, only tokens with a
trustworthy publish time inside the last two hours and no earlier than this alert
policy are checked for coverage. Older tokens, future timestamps, and missing
timestamps are reported as scope exclusions, not mint misses. An eligible leader
without an alert is marked for review; it is not proof of a miss because a
current one-hour board is not a historical fixed-window golden-dog label.
GeckoTerminal fallback data is reported as unavailable.

## Safety boundary

All current outputs are evidence and research artifacts. They do not authorize
real-money orders and do not establish that the system is profitable. The mint
alert path performs its own immutable fast qualification; the separate
`golden_dogs` evaluation remains the retrospective quality-measurement path.
