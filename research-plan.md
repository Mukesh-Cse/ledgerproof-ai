# Research plan

## Question

Given the same proposed banking code change, do tests focused on a business rule catch more defects before human review than additional routine examples for the same number of checks?

- **H1:** Business-rule checks will catch more seeded defects than the same number of routine checks.
- **H2:** Some defective changes will still clear the business-rule checks. Independent assessment should expose at least one gap that changes what a reviewer would ask.

## Experiment

Use six synthetic retail-banking rules, each with one conforming implementation and three intentional alternatives. Run the same 24 candidates through each of three workflows. A candidate is eligible for human review only when every check in that workflow passes. Every workflow runs its whole check set to make the evidence comparable.

| Workflow | Checks per candidate | Purpose |
| --- | ---: | --- |
| Smoke checks | 1 | Represent a minimal existing check |
| More routine examples | 3 | Control for the number of checks |
| Business-rule checks | 3 | Exercise two named boundary or exception conditions |

Use a separate audit suite to assign truth labels after the gate decisions are calculated. Its inputs differ from the gate inputs. Validate that each reference implementation passes the audit and each intentional defect fails it. Both the audit and the candidates are visible in the repository for reproduction. Keep all three arms fixed when replicating this run.

The primary measure is defective candidates that pass the gate divided by all audit-defective candidates. Report the paired comparisons, including disagreements in both directions. Also report conforming candidates held, exact check counts, and per-rule outcomes. Recalculate the matched comparison after dropping each rule in turn to see whether one rule drives the direction. Counts describe this deliberately constructed corpus. The fixtures and probes share an author and are designed to exercise recognisable failure modes, so sampling uncertainty and population-level effects are outside the scope of the benchmark.

The static comparison uses trusted, handwritten candidate functions. A passing workflow decision means the candidate is eligible for review, with approval reserved for a human reviewer.

## Follow-up study of the review agent

**Question.** Can an agent that chooses its own tests after reading a change reproduce defects that fixed, equally sized test suites miss? How often does it unnecessarily hold conforming changes?

- **H3:** In a fresh corpus, the agent will reproduce at least one material defect that both matched static workflows miss, while remaining within two probes per candidate.
- **H4:** Some agent holds will lack a cited failing probe. Review the associated rationale and track these as unconfirmed holds to assess the burden on reviewers.

Freeze the model version, tool protocol and acceptance criteria. Run each review in a fresh context that receives the requirement, smoke result and anonymised candidate source on request. Give both static arms and the agent the same smoke check and two additional checks. The agent can inspect source and ask the reference implementation to evaluate custom inputs, so this is a comparison of complete workflows, including the extra information and model effort required by the agent. Save elapsed time and API usage in an actual pilot if cost is a decision factor. Validate conclusions on fresh cases written by a separate author and reserve the audit cases for scoring. Record any exact overlap between agent probes and the audit set.

Report material defects held with an executable counterexample, defective candidates handed off, unconfirmed holds, conforming candidates held and incomplete reviews. Look at case-level disagreements with both static workflows. Report paired results over the same cases and list skipped or incomplete trials. The three recorded Codex tool sessions are informed walkthroughs and should stay outside any blinded performance estimate.
