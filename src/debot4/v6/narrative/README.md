# v6 narrative boundary

This package is independent of every pre-v6 narrative/source package and contains
no runtime loop. Its token, evidence, dossier, valuation, readiness, and
FxTwitter types are all v6-owned.

Input flow:

1. `LiveNarrativeRepository.research(...)` fetches only an exact X status URL.
2. `build_live_dossier(...)` accepts an exact-CA primary declaration and only
   strictly prior official DeBot KOL BUY facts. `READY` never authorizes a trade.
3. `build_executable_dossier(...)` classifies propagation, cultural fit,
   catalyst, leader competition, and consensus stage from the exact status,
   internally consistent DeBot social metadata, and repeated prior/current KOL
   waves. Missing evidence remains `WAIT`; contradictory contract context is
   `REJECT`. It seals the enriched dossier into the source research identity.
4. `evaluate_narrative_gate(...)` combines a completed narrative dossier,
   bounded valuation, immutable research result, and a fresh decision-time DeBot
   KOL/SmartMoney wave. It emits categorical `PASS`, `WAIT`, or `REJECT`.
5. `evaluate_execution_boundary(...)` rechecks an atomic route-and-FDV quote
   against the newest observed head. It emits `PASS`, `REQUOTE`, or `REJECT`.
6. `authorize_entry(...)` emits `COMMIT` only when both preceding decisions pass.

All outputs have canonical identities. There is no score, target-price guess,
DEX trigger, browser dependency, or permission to place real-money orders.
