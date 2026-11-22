"""Execute both ledger implementations with disposable synthetic bookings."""

from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from payment_ledger import PaymentLedger, validate_payment


def event_amount_without_account(conn, account_id, event_id):
    """An intentionally faulty lookup for the regression walkthrough."""
    row = conn.execute("SELECT minor_units FROM bookings WHERE event_id = ?", (event_id,)).fetchone()
    return row[0] if row else None


def payment_events(value):
    if not isinstance(value, (list, tuple)) or len(value) > 12:
        raise ValueError("Expected up to 12 synthetic payment deliveries")
    events = []
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            raise ValueError("Each delivery must contain an account ID, event ID and amount")
        validate_payment(*row)
        events.append(tuple(row))
    return tuple(events)


def run_ledger(events, *, lookup=None):
    with TemporaryDirectory(prefix="payment-review-", dir=Path.cwd()) as directory:
        path = Path(directory) / "payments.sqlite3"
        ledger = PaymentLedger(path) if lookup is None else PaymentLedger(path, lookup=lookup)
        receipts = [asdict(ledger.book(*event)) for event in events]
        return {"bookings": receipts, "total_minor_units": sum(ledger.totals().values())}


def compare_ledgers(deliveries):
    events = payment_events(deliveries)
    if not events:
        raise ValueError("Add at least one payment delivery")
    return {"current": run_ledger(events), "faulty": run_ledger(events, lookup=event_amount_without_account)}
