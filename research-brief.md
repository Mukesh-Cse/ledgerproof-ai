# Can an AI reviewer investigate a risky banking code change?

The [payment ledger vertical slice](implementation-plan.md) extends this study into an executable workflow. It reviews a transactional SQLite ledger and adds an agent-found counterexample to the fixed CI suite after human approval. The results below describe the original research corpus. [Interactive ledger demo](output/demo/index.html)

**Decision for a pilot.** Keep existing regression checks and trial a bounded AI reviewer on synthetic transaction changes. Ask reviewers to check the agent's counterexample, explain the business rule it tests, and identify a remaining question. Use blind adjudication to assess material defects and reviewer effort.

## What the review agent did

Codex used the project's tools to inspect source, run two probes per case, and submit a decision with evidence and a stakeholder question. In the payment trace, changing only the second account after a passing replay test exposed a missing booking. In the refund trace, changing only the request amount isolated a one-minor-unit shortfall. The same tool loop handed a conforming settlement candidate to a human after testing consecutive closures. [Payment trace](agent-traces/payment-retry.json) · [Refund trace](agent-traces/refund.json) · [Settlement trace](agent-traces/settlement.json)

These were selected demonstrations with prior fixture knowledge. They show how the workflow generates and adapts executable checks. The API loop has automated tests with a mocked transport, and the full-corpus live run remains open. Treat the separate static comparison below as evidence about fixed test selection.

## What the benchmark found

Six synthetic rules each had four candidate implementations, one conforming and three intentionally defective. Each candidate went through a smoke check, a three-check suite with more routine examples, and a three-check suite with two business-rule probes. A separate audit suite used different inputs to determine which candidates were defective. Both matched workflows ran 72 checks. The analysis counts a passing candidate as eligible for human review.

| Rule | Defects caught with smoke checks | More routine examples | Business-rule checks |
| --- | ---: | ---: | ---: |
| Fee rounding | 0/3 | 0/3 | 2/3 |
| Payment retries | 0/3 | 0/3 | 2/3 |
| Affordability | 0/3 | 1/3 | 2/3 |
| Statement windows | 0/3 | 0/3 | 2/3 |
| Partial refunds | 0/3 | 1/3 | 2/3 |
| Settlement dates | 1/3 | 1/3 | 2/3 |
| **Total** | **1/18** | **3/18** | **12/18** |

Business-rule checks caught 10 defects exclusively and routine checks caught one exclusively. Both caught two and both missed five. The business-rule workflow therefore caught nine more defects overall and reduced escapes from 15/18 to 6/18. All six conforming candidates cleared each workflow. Excluding any one rule left the business-rule workflow ahead by seven or eight catches across the remaining 15 defective candidates.

### Three cases to discuss

| Case | Observed behavior | Implication for a reviewer |
| --- | --- | --- |
| Duplicate delivery | A replay of a 100-minor-unit booking returned 200. Only the business-rule suite exposed this implementation. | Name the expected effect of replay before reviewing the change. |
| Event ID scope | Two accounts shared an event ID. The audit expected 36 minor units and observed 12. All workflows passed this implementation. | Ask whether event identity is account-scoped and test more than one account. |
| Exact refund balance | A request equal to the remaining 321 minor units returned 320 in the audit. The routine suite caught this defect at a different exact-balance amount. | Keep existing boundary examples when adding tests for over-refund and invalid requests. |

### What the evidence supports

H1 and H2 both held on these fixtures. The paired design isolates which check set caught each seeded defect, with identical candidates and matching check counts for the main comparison. The benchmark author selected the check sets, created the candidates and wrote the audit, so the design favors recognisable failures. The six conforming cases offer only a small sanity check on unnecessary holds. Equal check counts do little to establish equal authoring, maintenance or review effort. Estimates for live agents, delivery time and skills development require new observations.

## Benchmark against public research

| Source and finding | Implication for the follow-up study |
| --- | --- |
| SWE-bench evaluates model edits with executable tests on issues from real open-source repositories. Its setting includes broader repository context than these isolated rules. [Jimenez et al.](https://arxiv.org/abs/2310.06770) | Move from handwritten alterations to frozen agent-generated patches against realistic tickets. Keep assessment checks separate from agent-visible evidence. |
| METR's early-2025 randomized study found a 19% increase in implementation time with AI allowed for one set of experienced open-source developers. Its 2026 follow-up discusses selection effects as AI adoption widened. [Study](https://arxiv.org/abs/2507.09089) · [Follow-up](https://metr.org/blog/2026-02-24-uplift-update/) | Measure active review, rework and elapsed delivery time separately. Record tool version, task type and familiarity before interpreting any differences. |
| DORA describes AI as amplifying existing organizational strengths and weaknesses. [DORA 2025](https://dora.dev/research/2025/dora-report/) | Ask how teams capture rules, write acceptance criteria and hand off review. The quality of those inputs is a candidate explanation to investigate. |
| An Anthropic experiment found weaker immediate quiz performance among developers using AI to learn one new Python library. [Shen and Tamkin](https://www.anthropic.com/research/AI-assistance-coding-skills) | Add a brief unassisted exercise to test whether reviewers can transfer what they learned to a fresh rule. Treat lasting skill retention as a separate question. |

## Proposed pilot with a product team

**Recruit and scope.** Ask one retail-banking product team and one financing team to nominate domain owners, engineers and reviewers. Start with twelve synthetic tickets, allowing for both easy regressions and ambiguous edge cases. Ask domain owners to define the acceptance criteria and severity before seeing patches. Use approved tools and a sandbox for generating candidates, with independent evaluation in a separate environment.

**Isolate the review intervention.** Use one frozen generator version and a fixed prompt and iteration budget to produce one candidate per ticket. Record the run configuration, diff and failed or abandoned generations. Have two reviewers independently assess each available change. Both get the same diff, ticket and existing regression evidence. The intervention also gets the review agent's two-probe record and its stakeholder question. Label the generator and reviewer models separately if both are used. Randomise assignment within each reviewer pair and balance conditions across reviewers and ticket types. Each reviewer sees a candidate only once. A separate assessor who has no view of review assignments adjudicates the final defect labels. Report any missing pairs and keep generation failures visible in the study flow.

**Decide what would change the recommendation.** Use paired detection of adjudicated material defects as the primary outcome. Also record false holds, minutes spent reviewing, reviewer confidence, and unassisted performance on a different rule one week later. Set an acceptable review-time cost and a severity threshold with the product and risk owners before collecting outcomes. If material detection improves inside that budget, trial the workflow on a second set of tickets. If detection changes little or overhead dominates, review the failure traces with engineers and narrow the intervention. Treat a twelve-ticket pilot as directional evidence.

| Stakeholder | Question | What to collect |
| --- | --- | --- |
| Engineer or reviewer | Which checking step consumes the most time and where does a passing suite change your confidence? | Review sequence, active minutes and reasons for escalating or accepting a candidate. |
| Product owner or domain specialist | Which outcomes are unacceptable, and where would an engineer learn that today? | Named rules, source of truth, severity and examples that need to become acceptance criteria. |
| Quality or risk representative | What evidence is sufficient for a second reviewer to reproduce a decision? | Required evidence and examples of conditions that should trigger escalation. |
| Team lead or trainee | Can a reviewer spot a related error after the exercise without tool assistance? | Short transfer exercise and a follow-up discussion about documentation and training needs. |

**Learning exercise.** Give a reviewer the green `payment-retry/global-key` trace and ask them to write a counterexample. Ask them to teach back why account scope and replay behavior are separate questions. Repeat with a new statement-window rule to examine transfer beyond the worked example.
