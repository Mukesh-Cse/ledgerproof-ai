"""Run paired review policies over the same trusted candidates using Python 3.10+."""

import argparse
from datetime import date
import json
from pathlib import Path

from banking_cases import RULES, Candidate, Check, Rule


WORKFLOWS = {
    "smoke": "Smoke checks",
    "routine": "More routine examples",
    "focused": "Business-rule checks",
}


def check_candidate(candidate: Candidate, check: Check) -> dict:
    error = None
    actual = None
    try:
        actual = candidate.implementation(*check.args)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    return {
        "check": check.description,
        "inputs": check.args,
        "expected": check.expected,
        "actual": actual,
        "error": error,
        "passed": error is None and type(actual) is type(check.expected) and actual == check.expected,
    }


def evaluate(rule: Rule, candidate: Candidate) -> dict:
    check_sets = {
        "smoke": (rule.smoke,),
        "routine": (rule.smoke, *rule.routine),
        "focused": (rule.smoke, *rule.focused),
    }
    workflows = {}
    for workflow, check_set in check_sets.items():
        checks = [check_candidate(candidate, check) for check in check_set]
        workflows[workflow] = {
            "eligible_for_review": all(check["passed"] for check in checks),
            "checks": checks,
        }

    audit = [check_candidate(candidate, check) for check in rule.audit]
    return {
        "id": f"{rule.id}/{candidate.id}",
        "rule": rule.id,
        "requirement": rule.requirement,
        "candidate": candidate.id,
        "description": candidate.description,
        "workflows": workflows,
        "audit": {"defective": any(not check["passed"] for check in audit), "checks": audit},
    }


def summarize(cases):
    defective = [case for case in cases if case["audit"]["defective"]]
    conforming = [case for case in cases if not case["audit"]["defective"]]
    outcomes = {}
    for workflow in WORKFLOWS:
        escaped = sum(case["workflows"][workflow]["eligible_for_review"] for case in defective)
        outcomes[workflow] = {
            "defects_caught": len(defective) - escaped,
            "defects_escaped": escaped,
            "conforming_held": sum(not case["workflows"][workflow]["eligible_for_review"] for case in conforming),
            "checks": sum(len(case["workflows"][workflow]["checks"]) for case in cases),
        }
    return {"cases": len(cases), "defective": len(defective), "conforming": len(conforming), "workflows": outcomes}


def compare_matched_workflows(cases):
    outcomes = {"focused_only": [], "routine_only": [], "both": [], "neither": []}
    for case in cases:
        if not case["audit"]["defective"]:
            continue
        routine = not case["workflows"]["routine"]["eligible_for_review"]
        focused = not case["workflows"]["focused"]["eligible_for_review"]
        group = {
            (False, False): "neither",
            (True, False): "routine_only",
            (False, True): "focused_only",
            (True, True): "both",
        }[routine, focused]
        outcomes[group].append(case["id"])
    return outcomes


def run():
    cases = []
    for rule in RULES:
        gate_inputs = {check.args for check in (rule.smoke, *rule.routine, *rule.focused)}
        if gate_inputs.intersection(check.args for check in rule.audit):
            raise ValueError(f"Audit inputs overlap the gate inputs for {rule.id}")
        for candidate in rule.candidates:
            case = evaluate(rule, candidate)
            expected_defect = candidate.id != "reference"
            if case["audit"]["defective"] != expected_defect:
                raise ValueError(f"Unexpected audit verdict for {case['id']}")
            cases.append(case)

    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Candidate IDs must be unique")

    per_rule = {rule.id: summarize([case for case in cases if case["rule"] == rule.id]) for rule in RULES}
    sensitivity = {}
    for rule in RULES:
        comparison = compare_matched_workflows([case for case in cases if case["rule"] != rule.id])
        sensitivity[rule.id] = len(comparison["focused_only"]) - len(comparison["routine_only"])

    return {
        "schema_version": 1,
        "candidate_source": "handwritten synthetic implementations",
        "summary": summarize(cases),
        "matched_comparison": compare_matched_workflows(cases),
        "per_rule": per_rule,
        "additional_defects_caught_after_excluding_rule": sensitivity,
        "cases": cases,
    }


def print_summary(results):
    summary = results["summary"]
    print(f"{summary['cases']} synthetic candidates | {summary['defective']} defective | {summary['conforming']} conforming")
    print(f"{'Workflow':25} {'Caught':>10} {'Escaped':>10} {'Clean held':>12} {'Checks':>8}")
    for workflow, outcome in summary["workflows"].items():
        caught = f"{outcome['defects_caught']}/{summary['defective']}"
        escaped = f"{outcome['defects_escaped']}/{summary['defective']}"
        held = f"{outcome['conforming_held']}/{summary['conforming']}"
        print(f"{WORKFLOWS[workflow]:25} {caught:>10} {escaped:>10} {held:>12} {outcome['checks']:>8}")


def encode_json(value):
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def as_json(value):
    return json.dumps(value, indent=2, default=encode_json)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List candidate IDs")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--case", metavar="RULE/CANDIDATE", help="Print the check-by-check evidence for one candidate")
    output.add_argument("--json", type=Path, metavar="PATH", help="Write the complete run and evidence to a JSON file")
    args = parser.parse_args()
    if args.list and (args.case or args.json):
        parser.error("--list cannot be combined with --case or --json")

    results = run()
    if args.list:
        for case in results["cases"]:
            print(case["id"])
    elif args.case:
        cases = {case["id"]: case for case in results["cases"]}
        if args.case not in cases:
            parser.error(f"Unknown candidate {args.case!r}. Use --list to see candidate IDs.")
        print(as_json(cases[args.case]))
    else:
        print_summary(results)
        if args.json:
            args.json.write_text(as_json(results) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
