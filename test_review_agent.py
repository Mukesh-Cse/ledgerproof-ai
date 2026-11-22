import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from benchmark import as_json
from review_agent import (
    CASES, HOLD, READY, OpenAIReviewer, apply_action, open_review, run_model, score,
    visible_context,
)


CASE = "payment-retry/global-key"
COLLISION = [[['account-a', 'event-1', 7], ['account-b', 'event-1', 12]]]


class ReviewAgentTests(unittest.TestCase):
    def test_context_and_source_keep_score_and_fixture_identifiers_private(self):
        for case_id in CASES:
            with self.subTest(case=case_id):
                session = open_review(case_id, {"type": "test"})
                source = apply_action(session, "inspect_candidate", {})["python"]
                score(session)
                tree = as_json(visible_context(session))
                self.assertIn("def candidate(", source)
                self.assertNotIn(case_id, tree)
                self.assertNotIn("audit_defective", tree)
                self.assertNotIn("audit_failed_checks", tree)

    def test_failed_probe_blocks_readiness_and_probes_are_bounded(self):
        session = open_review(CASE, {"type": "test"})
        apply_action(session, "inspect_candidate", {})
        malformed = {"inputs_json": json.dumps([[['a', 'e', True]]]), "hypothesis": "Reject a boolean amount."}
        self.assertIn("error", apply_action(session, "run_probe", malformed))
        probe = {"inputs_json": json.dumps(COLLISION), "hypothesis": "Event ID scope across accounts."}
        self.assertFalse(apply_action(session, "run_probe", probe)["passed"])
        self.assertEqual(apply_action(session, "run_probe", probe)["id"], "probe-2")
        self.assertIn("error", apply_action(session, "run_probe", probe))
        assessment = {"evidence": ["probe-1"], "rationale": "The second booking is missing.", "stakeholder_question": "Are IDs account-scoped?"}
        self.assertIn("error", apply_action(session, "submit_review", {"decision": READY, **assessment}))
        self.assertTrue(apply_action(session, "submit_review", {"decision": HOLD, **assessment})["accepted"])
        self.assertTrue(score(session)["cited_failing_probe"])

    def test_api_loop_observes_each_tool_result_before_next_action(self):
        decisions = iter([
            ("inspect_candidate", {}),
            ("run_probe", {"inputs_json": json.dumps(COLLISION), "hypothesis": "Check accounts sharing IDs."}),
            ("submit_review", {
                "decision": HOLD, "evidence": ["probe-1"], "rationale": "A legitimate booking was dropped.",
                "stakeholder_question": "Where is event identity defined?",
            }),
        ])
        observed = []

        def transport(request, timeout):
            payload = json.loads(request.data)
            self.assertIs(payload["store"], False)
            self.assertFalse(payload["parallel_tool_calls"])
            observed.append(json.loads(payload["input"]))
            name, args = next(decisions)
            return io.BytesIO(json.dumps({
                "status": "completed", "model": "test-model",
                "output": [{"type": "function_call", "name": name, "arguments": json.dumps(args)}],
            }).encode())

        session = open_review(CASE, {"type": "test"})
        with patch("review_agent.urlopen", side_effect=transport):
            run_model(session, OpenAIReviewer("test-model", "mock-key"))
        self.assertEqual([len(context["actions"]) for context in observed], [0, 1, 2])
        self.assertFalse(observed[2]["actions"][-1]["result"]["passed"])
        self.assertTrue(session["assessment"]["cited_failing_probe"])

    def test_recorded_model_driven_traces_replay(self):
        root = Path(__file__).parent
        files = sorted((root / "agent-traces").glob("*.json"))
        files.extend(sorted((root / "evidence").glob("ledger-agent-*.json")))
        self.assertEqual(len(files), 5)
        for path in files:
            recorded = json.loads(path.read_text(encoding="utf-8"))
            reproduced = open_review(recorded["case_id"], recorded["backend"])
            for step in recorded["actions"]:
                actual = apply_action(reproduced, step["tool"], step["arguments"])
                self.assertEqual(json.loads(as_json(actual)), step["result"])
            self.assertEqual(score(reproduced), recorded["assessment"])


if __name__ == "__main__":
    unittest.main()
