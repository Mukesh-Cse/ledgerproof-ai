# Payment Change Review

[![Payment review CI](https://github.com/Mukesh-Cse/payment-change-review/actions/workflows/payment-review.yml/badge.svg?branch=main)](https://github.com/Mukesh-Cse/payment-change-review/actions/workflows/payment-review.yml)

**Two accounts share an event ID. The replay test passes. One valid booking disappears.** Changing only the second account exposed an 850-minor-unit shortfall in a transactional SQLite ledger. A Codex-driven reviewer reproduced the failure in two probes. The approved counterexample now runs as a permanent CI test without a model.

**[Try the live payment sandbox](https://mukesh-cse.github.io/payment-change-review/)** · [Recorded agent walkthrough](https://mukesh-cse.github.io/payment-change-review/walkthrough/) · [One-page case study](output/pdf/banking-code-review-brief.pdf) · [Pilot and operating plan](implementation-plan.md)

Click **Run both ledgers** to reproduce the missing booking, or edit the sample account, event ID and amount. The browser runs both Python/SQLite implementations on the same inputs and shows which bookings each one accepted or suppressed. Each run starts with a fresh database. The first run loads a pinned Pyodide runtime. The recorded agent walkthrough is also available as a [downloadable HTML file](output/demo/index.html).

| Probe | Faulty ledger | Current ledger |
| --- | ---: | ---: |
| Replay the same event in the original account | 1,200 | 1,200 |
| Change only the account on the second event | **1,200** | **2,050** |

Both runs use synthetic payments. Amounts are in minor units. The agent received the ticket and source excerpt, chose each probe, and cited the observed failure in its handoff. A separate audit scored the review after the decision. The Codex walkthroughs used known fixtures. Blinded model accuracy and production throughput remain open questions.

## Run it locally

Clone the repository and use Python 3.10 or later. The standard-library path runs offline in a writable directory with no API key.

```text
git clone https://github.com/Mukesh-Cse/payment-change-review.git
cd payment-change-review
python -m unittest -v
python payment_review.py
python payment_review.py --candidate global-id-regression
python payment_load.py --workers 8
```

The deliberate regression exits `1` and prints expected and observed totals. Pass `--output PATH` to `payment_review.py` or `payment_load.py` to save a fresh JSON report. Run `python build_demo.py` to rebuild the offline HTML from the committed evidence. The browser walkthrough includes the source excerpt, test inputs and a downloadable review trace.

## Preview or deploy the recruiter site

```text
python build_pages.py
python -m http.server 8000 --bind 127.0.0.1 --directory _site
```

Open `http://127.0.0.1:8000/`. The build puts the live sandbox, recorded walkthrough and PDF in `_site/`. The [Pages workflow](.github/workflows/recruiter-demo.yml) builds that directory from `main` and deploys it to GitHub Pages. A fork can enable **GitHub Actions** as its Pages source and run the same workflow. The [live sandbox](payment_sandbox.py) and the CLI share the repository’s payment implementation. User-entered payments stay in the browser. Live model evaluations use the separate, opt-in API CLI.

## See the evidence become a regression test

The [held review](evidence/ledger-agent-hold.json) and [current ledger review](evidence/ledger-agent-ready.json) execute the same payment path in disposable SQLite databases. The [permanent suite](payment-regressions.json) retains the accepted probe’s inputs, expected amount and source-trace fingerprint. The command below is idempotent. It reports that the committed inputs are already registered.

```text
python payment_review.py --promote evidence/ledger-agent-hold.json --probe probe-2 --name "Allow the same event ID across accounts"
```

The [GitHub Actions workflow](.github/workflows/payment-review.yml) runs the checks against the checked-out ledger and uploads the revision and evidence JSON. The [recorded local run](evidence/load.json) exercised 800 deliveries across eight workers. It booked 200 unique payments, suppressed 600 replays and matched every account total. The concurrency run checks correctness and gives a local timing reference.

## Research prototype

The original 24-case study tests fixed review policies across six synthetic banking rules. The agent also works on those cases. The agent discloses its decision and evidence IDs before the separate audit scores it.

### Earlier walkthroughs

1. **Inspect.** The source keys payment events on event ID, while the ticket describes an account-scoped ID.
2. **Test.** A replay inside one account preserved the first booking as expected.
3. **Adapt.** The agent changed only the second account. The candidate returned **45 minor units where 135 were due**.
4. **Handoff.** The agent held the change, cited the failing probe and asked the payment domain owner whether channels share the same event-ID scope.

Codex chose and executed the steps through the project's tools in three walkthroughs. Both defective candidates were held with a failing probe, and one conforming candidate was handed off for human review. The cases were selected with prior fixture knowledge. Use the traces to inspect how the agent works. A blinded full-corpus run is needed to estimate its accuracy.

| Trace | Tool result | Decision |
| --- | --- | --- |
| [Payment retry](agent-traces/payment-retry.json) | Cross-account event collision returned 45 instead of 135 minor units | Hold |
| [Exact refund](agent-traces/refund.json) | Equality branch returned 569 instead of 570 minor units | Hold |
| [Settlement date](agent-traces/settlement.json) | Consecutive closures shifted settlement to the next open weekday | Ready for human review |

### Run the agent

Use Python 3.10 or later. The CLI uses the standard library. The recorded traces, static benchmark, external model tool interface and tests run offline.

```text
python -m unittest -v
python review_agent.py --list
```

To run the automated reviewer, set `OPENAI_API_KEY` in your environment and replace `YOUR_MODEL_ID` with a model in your account that supports Responses API function calling. The live mode sends synthetic source, test data and tool results to the model API. It makes at most seven model calls per case, executes up to two additional probes and writes a JSON report with decisions, outcomes and tool evidence. The API-backed path was verified with a mocked transport. No live API batch has been run.

```text
python review_agent.py --case payment-ledger/current --model YOUR_MODEL_ID --output live-review.json
python review_agent.py --all --model YOUR_MODEL_ID --output live-batch.json
```

The same tools can be driven by an external model in a chat or a human operator. Start a session, give the operator the CLI's ticket output, and pass each chosen tool action back to the CLI in turn. Use a fresh output file for a new review. Keep the fixture identifier and final assessment out of the operator's context for a blind run.

```powershell
python review_agent.py --case payment-retry/global-key --actor 'External model' --output review.json
python review_agent.py --resume review.json --action '{"tool":"inspect_candidate","arguments":{}}'
```

The other tool actions are `run_probe` with `hypothesis` and `inputs_json` (a string containing a JSON argument array), and `submit_review` with `decision`, `evidence` (an array of returned IDs), `rationale`, and `stakeholder_question`. Decisions are `hold` or `ready_for_human_review`.

### Static benchmark for comparison

Three fixed review policies establish a baseline on 24 handwritten candidates across six synthetic rules. The paired design holds candidate behavior fixed when comparing test selection.

| Review policy | Checks per candidate | Seeded defects caught | Seeded defects that passed | Conforming candidates held |
| --- | ---: | ---: | ---: | ---: |
| Smoke checks | 1 | 1/18 | 17/18 | 0/6 |
| More routine examples | 3 | 3/18 | 15/18 | 0/6 |
| Business-rule checks | 3 | **12/18** | **6/18** | 0/6 |

The matched policies ran 72 checks each. Business-rule checks caught 10 defects that routine checks missed. Routine checks alone caught an exact-balance refund that returned one minor unit too little. Both policies missed a payment retry bug that dropped a legitimate booking when two accounts shared an event ID. This suggests keeping routine regressions in the review workflow and asking domain owners which invariants the tests are missing.

```text
python benchmark.py
python benchmark.py --case payment-retry/global-key
python benchmark.py --json results.json
```

`results.json` contains the static traces, paired outcomes and leave-one-rule-out check. It also gives the independent audit outcomes for each case.

## Repository map

| Area | Start here |
| --- | --- |
| Ledger and operational checks | [SQLite ledger](payment_ledger.py), [ledger tests](test_payment_ledger.py), [concurrency driver](payment_load.py) |
| Agent review and human handoff | [Agent tools and API adapter](review_agent.py), [agent tests](test_review_agent.py), [promotion and CI](payment_review.py) |
| Research method and results | [Research plan](research-plan.md), [findings and pilot](research-brief.md), [benchmark runner](benchmark.py), [recorded run](results.json) |
| Portfolio and implementation | [One-page case study](output/pdf/banking-code-review-brief.pdf), [scaling and ownership](implementation-plan.md), [interview walkthrough](application-notes.md) |

Independent portfolio work. All rules, examples and data are synthetic.
