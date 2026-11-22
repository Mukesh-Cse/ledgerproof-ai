"""Review the payment ledger in this checkout and emit a CI evidence artifact."""

import argparse
from functools import partial
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from banking_cases import Candidate, Check, Rule, booking_total
from benchmark import as_json, check_candidate, evaluate
from payment_ledger import account_event_amount
from payment_sandbox import event_amount_without_account, payment_events, run_ledger


DEFAULT_SUITE = Path(__file__).with_name("payment-regressions.json")


def trace_fingerprint(trace):
    canonical = json.dumps(trace, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(canonical.encode("utf-8")).hexdigest()


def database_total(events, *, lookup=None):
    return run_ledger(events, lookup=lookup)["total_minor_units"]


LEDGER_RULE = Rule(
    "payment-ledger",
    "Book each (account ID, event ID) once and keep the first amount on replay. "
    "The same event ID in two accounts must produce two bookings. Amounts are positive integer minor units. "
    "The source excerpt is the lookup inside the SQLite write transaction, and probes run the whole booking path.",
    (
        Candidate("reference", "Independent in-memory booking specification", booking_total),
        Candidate("current", "Payment ledger in this checkout", database_total, account_event_amount),
        Candidate("global-id-regression", "Known faulty ledger lookup for a demo", partial(database_total, lookup=event_amount_without_account), event_amount_without_account),
    ),
    Check("Distinct payments for one account", ((('one', 'p1', 101), ('one', 'p2', 202)),), 303),
    (
        Check("Empty ledger", ((),), 0),
        Check("Two accounts with distinct IDs", ((('one', 'p3', 310), ('two', 'p4', 423)),), 733),
    ),
    (
        Check("Replay preserves original booking", ((('one', 'p5', 421), ('one', 'p5', 499)),), 421),
        Check("Same event ID may appear in two accounts", ((('one', 'p6', 155), ('two', 'p6', 268)),), 423),
    ),
    (
        Check("Reused ID plus a duplicate in one account", ((('a', 'p7', 530), ('b', 'p7', 640), ('a', 'p7', 999)),), 1170),
        Check("Two distinct events with equal amounts", ((('a', 'p8', 78), ('a', 'p9', 78)),), 156),
    ),
)


def load_suite(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("checks"), list):
        raise ValueError("Unsupported payment regression suite")
    return data


def ci_review(candidate, revision=None, curated=()):
    review = evaluate(LEDGER_RULE, candidate)
    focused = review["workflows"]["focused"]["eligible_for_review"]
    promoted = []
    for case in curated:
        events = payment_events(case["events"])
        expected = booking_total(events)
        if type(case["expected_minor_units"]) is not int or case["expected_minor_units"] != expected:
            raise ValueError(f"Curated check {case['name']!r} disagrees with the payment specification")
        promoted.append(check_candidate(candidate, Check(case["name"], (events,), expected)))
    passed = focused and not review["audit"]["defective"] and all(check["passed"] for check in promoted)
    return {
        "revision": revision,
        "decision": "ready_for_human_review" if passed else "hold",
        "review": review,
        "promoted_checks": promoted,
    }


def promote_probe(trace_path, probe_id, name, suite_path):
    """After reviewer sign-off, turn a cited, executable counterexample into a fixed check."""
    if not 1 <= len(name.strip()) <= 100:
        raise ValueError("Provide a reviewable regression-check name")
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    decision = trace.get("decision") or {}
    if not trace.get("case_id", "").startswith("payment-ledger/") or decision.get("decision") != "hold":
        raise ValueError("Only a held payment-ledger review can supply a regression check")
    if probe_id not in decision.get("evidence", []):
        raise ValueError("The decision must cite the probe")
    for step in trace["actions"]:
        probe = step["result"]
        if step["tool"] == "run_probe" and probe.get("id") == probe_id and probe.get("passed") is False:
            break
    else:
        raise ValueError("Could not find a cited failing probe")

    if not isinstance(probe.get("inputs"), list) or len(probe["inputs"]) != 1:
        raise ValueError("A ledger probe must supply one list of deliveries")
    events = payment_events(probe["inputs"][0])
    expected = booking_total(events)
    if probe.get("expected") != expected or type(probe.get("actual")) is not int or probe["actual"] == expected:
        raise ValueError("The probe must record a concrete discrepancy against the independent specification")
    if database_total(events) != expected:
        raise ValueError("Fix the current ledger before adding this check to the required suite")
    lock_path = suite_path.with_suffix(suite_path.suffix + ".lock")
    try:
        lock = lock_path.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise ValueError("The regression suite is already being updated") from exc
    try:
        with lock:
            suite = load_suite(suite_path)
            for case in suite["checks"]:
                if payment_events(case["events"]) == events:
                    return False
                if case["name"].casefold() == name.strip().casefold():
                    raise ValueError("This regression-check name is already in use")
            suite["checks"].append({
                "name": name.strip(), "events": events, "expected_minor_units": expected,
                "evidence": {"case": trace["case_id"], "probe": probe_id, "sha256": trace_fingerprint(trace)},
            })
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=suite_path.parent, delete=False) as temporary:
                temp_path = Path(temporary.name)
                try:
                    temporary.write(as_json(suite) + "\n")
                    temporary.close()
                    temp_path.replace(suite_path)
                finally:
                    temporary.close()
                    temp_path.unlink(missing_ok=True)
        return True
    finally:
        lock_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    candidates = {candidate.id: candidate for candidate in LEDGER_RULE.candidates[1:]}
    parser.add_argument("--candidate", choices=candidates, default="current")
    parser.add_argument("--output", type=Path, help="Write detailed evidence as JSON")
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--promote", type=Path, metavar="TRACE", help="Add a manually approved failing probe as a required CI check")
    parser.add_argument("--probe", metavar="ID")
    parser.add_argument("--name", metavar="TEXT")
    args = parser.parse_args()
    if args.promote:
        if not args.probe or not args.name or args.output or args.candidate != "current":
            parser.error("Promotion requires --probe and --name alongside --promote and an optional --suite")
        try:
            added = promote_probe(args.promote, args.probe, args.name, args.suite)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            parser.error(str(exc))
        print("Regression check added" if added else "These inputs are already in the regression suite")
        return
    if args.probe or args.name:
        parser.error("--probe and --name require --promote")
    report = ci_review(candidates[args.candidate], os.environ.get("GITHUB_SHA"), load_suite(args.suite)["checks"])
    if args.output:
        args.output.write_text(as_json(report) + "\n", encoding="utf-8")
    print(f"{args.candidate}: {report['decision']}")
    for check in report["review"]["workflows"]["focused"]["checks"] + report["review"]["audit"]["checks"] + report["promoted_checks"]:
        if not check["passed"]:
            print(f"  {check['check']}: expected {check['expected']}, observed {check['actual']}")
    raise SystemExit(int(report["decision"] == "hold"))


if __name__ == "__main__":
    main()
