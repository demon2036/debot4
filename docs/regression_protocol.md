# DeBot4 regression protocol

This protocol replaces threshold tuning by intuition with a reproducible
champion/challenger process. A change cannot advance merely because a chart
looks better or a missed mover would have passed after the fact.

## Non-negotiable rule

Every candidate begins with a pre-registered experiment definition. It names
one hypothesis, one primary metric, one allowed change, an exact immutable data
slice, and failure conditions. The generated manifest binds that definition to
the code, all production configuration, the narrative prompt, model name, and
the append-only ledger hash.

If two runs do not share the same dataset identity, they are not a regression
comparison. If more than one causal variable changed, the result is diagnostic
only and cannot replace the champion.

## Regression ladder

1. **R0 — reproducibility:** freeze the experiment manifest and data watermark.
2. **R1 — engineering invariants:** unit, restart, no-lookahead, identity, and
   quote-boundary tests pass.
3. **R2 — deterministic replay:** champion and challenger see the same events in
   `(available_at, sequence)` order under a virtual clock. Repeating a run must
   reproduce every decision hash. Network and retrospective LLM calls are
   forbidden.
4. **R3 — data-plane SLA:** persist every poll attempt, success, unchanged
   response, failure, latency, provider, block lag, and payload age. Price-plane
   failure is evaluated independently from X/TG/DeBot/wallet intelligence.
5. **R4 — strategy outcomes:** label every discovered token episode over fixed
   5m/30m/1h/6h/24h horizons. Unknown coverage stays unknown. Reports separate
   discovery misses, missing data, strategy rejects, execution rejects, and
   portfolio-capacity rejects.
6. **R5 — execution:** collect exact entry and reverse quotes for accepted
   candidates and a pre-registered sample of near misses. Include gas, tax,
   failed exits, latency, and same-block market-cap reconstruction.
7. **R6 — promotion:** a single-change challenger must beat the frozen champion
   on the pre-registered metric without violating any earlier gate, then pass a
   frozen forward shadow/paper period.

## Required experiment lifecycle

```text
hypothesis
  -> immutable manifest
  -> engineering tests
  -> same-data deterministic replay
  -> paired champion/challenger comparison
  -> forward shadow
  -> forward paper
  -> promote or reject
```

Changing a threshold, prompt, model, data provider, latency, risk limit, or exit
rule starts a new experiment. Runs are never edited in place.

## Baselines

At minimum every strategy is compared with:

- no-trade;
- earliest safe-and-sellable discovery;
- quant-only liquidity/momentum;
- narrative-only after exact contract binding;
- the current frozen champion.

The unit of evaluation is a token/pair discovery episode, not each repeated
snapshot. Train/validation/test splits are chronological and purged by the
longest outcome horizon to prevent overlap leakage.

## Promotion evidence

Infrastructure must first show continuous source-health telemetry and a fast
price plane whose failures are isolated from slow intelligence sources. Paper
promotion then requires a pre-registered minimum sample of complete exact-quote
round trips, positive net expectancy after all modeled costs, controlled
drawdown, stable results across time blocks, and paired superiority to the best
simple baseline. A single lucky token cannot dominate the result.

`$100 -> $300/day` can be observed, but it cannot be used as a promise or as a
threshold-tuning target.
