"""Package the browser sandbox, recorded walkthrough and case study for static hosting."""

from pathlib import Path
from shutil import copyfile

from build_demo import build_demo


ROOT = Path(__file__).resolve().parent
ASSETS = {
    "index.html": "recruiter-demo/index.html",
    "recruiter.css": "recruiter-demo/recruiter.css",
    "recruiter.js": "recruiter-demo/recruiter.js",
    "ledger-worker.js": "recruiter-demo/ledger-worker.js",
    "payment_ledger.py": "payment_ledger.py",
    "payment_sandbox.py": "payment_sandbox.py",
    "brief.pdf": "output/pdf/banking-code-review-brief.pdf",
}


def build_pages():
    destination = ROOT / "_site"
    destination.mkdir(exist_ok=True)
    walkthrough = destination / "walkthrough"
    walkthrough.mkdir(exist_ok=True)
    copyfile(build_demo(), walkthrough / "index.html")
    for filename, source in ASSETS.items():
        copyfile(ROOT / source, destination / filename)
    return destination


if __name__ == "__main__":
    print(build_pages())
