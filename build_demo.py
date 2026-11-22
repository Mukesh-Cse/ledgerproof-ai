"""Build the self-contained recruiter demo from recorded evidence."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def build_demo():
    files = {
        "hold": "evidence/ledger-agent-hold.json",
        "ready": "evidence/ledger-agent-ready.json",
        "load": "evidence/load.json",
        "ci": "evidence/regression-ci.json",
    }
    evidence = {name: json.loads((ROOT / path).read_text(encoding="utf-8")) for name, path in files.items()}
    payload = json.dumps(evidence, ensure_ascii=True).replace("<", "\\u003c")
    template = (ROOT / "demo-template.html").read_text(encoding="utf-8")
    output = ROOT / "output" / "demo" / "index.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template.replace("__REVIEW_EVIDENCE__", payload), encoding="utf-8")
    return output


if __name__ == "__main__":
    print(build_demo())
