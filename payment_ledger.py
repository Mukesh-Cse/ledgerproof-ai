"""A transactional SQLite ledger for synthetic payment-event intake."""

from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class Booking:
    booked: bool
    recorded_minor_units: int
    amount_matches: bool


def account_event_amount(conn: sqlite3.Connection, account_id: str, event_id: str) -> int | None:
    row = conn.execute(
        "SELECT minor_units FROM bookings WHERE account_id = ? AND event_id = ?",
        (account_id, event_id),
    ).fetchone()
    return row[0] if row else None


def validate_payment(account_id: str, event_id: str, minor_units: int) -> None:
    for identifier in (account_id, event_id):
        if type(identifier) is not str or not identifier.strip() or len(identifier) > 40:
            raise ValueError("Account and event IDs must contain 1 to 40 characters")
    if type(minor_units) is not int or not 1 <= minor_units <= 1_000_000_000:
        raise ValueError("A payment must use 1 to 1,000,000,000 integer minor units")


class PaymentLedger:
    def __init__(
        self, path: Path, *, lookup: Callable[[sqlite3.Connection, str, str], int | None] = account_event_amount,
    ):
        self.path = path
        self.lookup = lookup
        with closing(self.connect()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    account_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    minor_units INTEGER NOT NULL CHECK (minor_units BETWEEN 1 AND 1000000000),
                    PRIMARY KEY (account_id, event_id)
                ) WITHOUT ROWID
            """)

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5.0)

    def book(self, account_id: str, event_id: str, minor_units: int) -> Booking:
        validate_payment(account_id, event_id, minor_units)

        # Acquire the writer lock before checking and inserting an event.
        with closing(self.connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            previous = self.lookup(conn, account_id, event_id)
            if previous is not None:
                return Booking(False, previous, previous == minor_units)
            conn.execute("INSERT INTO bookings VALUES (?, ?, ?)", (account_id, event_id, minor_units))
        return Booking(True, minor_units, True)

    def totals(self) -> dict[str, int]:
        with closing(self.connect()) as conn:
            rows = conn.execute("SELECT account_id, SUM(minor_units) FROM bookings GROUP BY account_id ORDER BY account_id")
            return dict(rows)
