"""Measure synthetic retry handling and check booking totals under local concurrency."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from math import ceil
from pathlib import Path
import platform
from random import Random
import sqlite3
from tempfile import TemporaryDirectory
from time import perf_counter

from benchmark import as_json
from payment_ledger import PaymentLedger


def exercise(path, accounts, events_per_account, deliveries_per_event, workers):
    ledger = PaymentLedger(path)
    deliveries = [
        (f"account-{account}", f"event-{event}", event + 1)
        for account in range(accounts)
        for event in range(events_per_account)
        for _ in range(deliveries_per_event)
    ]
    Random(2027).shuffle(deliveries)

    def book(event):
        started = perf_counter()
        result = ledger.book(*event)
        return result.booked, (perf_counter() - started) * 1000

    started = perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(book, deliveries))
    elapsed = perf_counter() - started
    recorded = sum(booked for booked, _ in results)
    latencies = sorted(latency for _, latency in results)
    expected_total = events_per_account * (events_per_account + 1) // 2
    totals_match = ledger.totals() == {f"account-{account}": expected_total for account in range(accounts)}
    return {
        "accounts": accounts, "workers": workers, "attempted_deliveries": len(deliveries),
        "booked_events": recorded, "suppressed_replays": len(deliveries) - recorded,
        "expected_events": accounts * events_per_account, "account_totals_match": totals_match,
        "p95_attempt_ms": round(latencies[ceil(0.95 * len(latencies)) - 1], 2),
        "deliveries_per_second": round(len(deliveries) / elapsed, 1),
        "environment": {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version, "os": platform.system()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, choices=(1, 2, 4, 8, 16), default=8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="payment-load-", dir=Path.cwd()) as directory:
        report = exercise(Path(directory) / "ledger.sqlite3", 8, 25, 4, args.workers)
    if args.output:
        args.output.write_text(as_json(report) + "\n", encoding="utf-8")
    print(as_json(report))
    raise SystemExit(int(not report["account_totals_match"] or report["booked_events"] != report["expected_events"]))


if __name__ == "__main__":
    main()
