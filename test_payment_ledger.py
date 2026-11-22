from pathlib import Path
from contextlib import closing
import json
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from payment_ledger import Booking, PaymentLedger
from payment_load import exercise
from payment_review import LEDGER_RULE, ci_review, load_suite, promote_probe, trace_fingerprint


class PaymentLedgerTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "payments.sqlite3"

    def test_cross_account_ids_and_changed_replays_survive_reopen(self):
        ledger = PaymentLedger(self.path)
        self.assertEqual(ledger.book("a", "shared", 45), Booking(True, 45, True))
        self.assertEqual(ledger.book("a", "shared", 90), Booking(False, 45, False))
        self.assertEqual(ledger.book("b", "shared", 90), Booking(True, 90, True))
        self.assertEqual(PaymentLedger(self.path).totals(), {"a": 45, "b": 90})

    def test_rejected_input_has_no_side_effects(self):
        ledger = PaymentLedger(self.path)
        for account, amount in (("", 100), ("a", True), ("a", -1), ("a", 1_000_000_001)):
            with self.subTest(account=account, amount=amount), self.assertRaises(ValueError):
                ledger.book(account, "p1", amount)
        self.assertEqual(ledger.totals(), {})

    def test_failed_write_rolls_back_and_retry_can_book(self):
        ledger = PaymentLedger(self.path)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.executescript("""
                CREATE TRIGGER simulated_failure AFTER INSERT ON bookings
                BEGIN SELECT RAISE(ABORT, 'simulated failure'); END;
            """)
            with self.assertRaises(sqlite3.IntegrityError):
                ledger.book("a", "p1", 50)
            self.assertEqual(ledger.totals(), {})
            conn.execute("DROP TRIGGER simulated_failure")
        self.assertTrue(ledger.book("a", "p1", 50).booked)
        self.assertEqual(ledger.totals(), {"a": 50})

    def test_concurrent_retries_book_only_once_per_account(self):
        report = exercise(self.path, accounts=4, events_per_account=3, deliveries_per_event=4, workers=8)
        self.assertEqual(report["attempted_deliveries"], 48)
        self.assertEqual(report["booked_events"], 12)
        self.assertEqual(report["suppressed_replays"], 36)
        self.assertTrue(report["account_totals_match"])

    def test_ci_check_holds_the_known_regression_and_passes_current_code(self):
        _, current, regression = LEDGER_RULE.candidates
        self.assertEqual(ci_review(current)["decision"], "ready_for_human_review")
        failed = ci_review(regression)
        self.assertEqual(failed["decision"], "hold")
        self.assertTrue(failed["review"]["workflows"]["smoke"]["eligible_for_review"])
        check = failed["review"]["workflows"]["focused"]["checks"][-1]
        self.assertEqual((check["expected"], check["actual"]), (423, 155))

    def test_reviewed_probe_can_be_promoted_exactly_once(self):
        trace = Path(__file__).with_name("evidence") / "ledger-agent-hold.json"
        suite = self.path.with_suffix(".json")
        suite.write_text(json.dumps({"schema_version": 1, "checks": []}), encoding="utf-8")
        self.assertTrue(promote_probe(trace, "probe-2", "Cross-account event replay", suite))
        original = suite.read_bytes()
        self.assertFalse(promote_probe(trace, "probe-2", "Cross-account event replay", suite))
        self.assertEqual(suite.read_bytes(), original)
        with self.assertRaises(ValueError):
            promote_probe(trace, "probe-1", "Passing probe", suite)
        lock = suite.with_suffix(".json.lock")
        lock.touch()
        with self.assertRaisesRegex(ValueError, "already being updated"):
            promote_probe(trace, "probe-2", "Cross-account event replay", suite)
        self.assertTrue(lock.exists())
        _, current, regression = LEDGER_RULE.candidates
        checks = load_suite(suite)["checks"]
        self.assertTrue(ci_review(current, curated=checks)["promoted_checks"][0]["passed"])
        probe = ci_review(regression, curated=checks)["promoted_checks"][0]
        self.assertEqual((probe["expected"], probe["actual"]), (2050, 1200))

    def test_committed_regression_fingerprint_matches_recorded_evidence(self):
        root = Path(__file__).parent
        trace = json.loads((root / "evidence/ledger-agent-hold.json").read_text(encoding="utf-8"))
        checks = load_suite(root / "payment-regressions.json")["checks"]
        self.assertEqual(checks[0]["evidence"]["sha256"], trace_fingerprint(trace))
