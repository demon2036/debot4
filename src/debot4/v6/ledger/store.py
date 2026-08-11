"""Public facade for the independent v6 SQLite ledger."""

from .database import LedgerCore
from .decisions import DecisionLedgerMixin
from .heads import HeadLedgerMixin
from .outcomes import OutcomeLedgerMixin
from .queries import QueryLedgerMixin
from .signals import SignalLedgerMixin
from .trades import TradeLedgerMixin


class V6Ledger(
    QueryLedgerMixin,
    OutcomeLedgerMixin,
    HeadLedgerMixin,
    TradeLedgerMixin,
    DecisionLedgerMixin,
    SignalLedgerMixin,
    LedgerCore,
):
    """Append-only ledger for the deliberately small v6 execution path."""
