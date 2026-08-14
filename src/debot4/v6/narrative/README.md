# v6 narrative boundary

This package is independent of every pre-v6 narrative/source package. Its
adapters, domain rules, persistence, runtime, and presentation boundaries are
v6-owned.

Exact CA location flow:

1. `BscMintMonitor` polls included BSC heads every 250 ms and reads canonical
   ERC-20 `Transfer` logs whose sender is the zero address. A positive mint log
   emitted by an address ending in the reviewed Flap `7777` suffix locates the
   Exact CA without depending on a mutable factory/router address. Latest-block
   evidence is explicitly included but not finalized and infers no launchpad.
2. `NarrativeMintMonitor` polls DeBot's `new` stage every second and persists
   every Exact CA, including tokens with no creation time or social link.
3. `MintLocationStore` bounds raw evidence to one day, 20,000 rows, and a
   64 MiB SQLite page ceiling. Raw locations never queue Grok and never
   authorize a trade.
4. `CatalystMintState` separately joins a reviewed X post only when mint
   metadata references the exact status ID inside the strict time window. Only
   this hard binding may enter narrative research.

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
