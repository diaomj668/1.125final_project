# Instructor Requirements and Proposal Alignment Audit

## Scope and authority

Reviewed the instructor's **Problem Set 06: Term Project Proposal**, all five pages, the student's five-page `proposal.pdf`, the one-slide `tuesday_overview.pptx`, and the current deployment source. The supplied instructor document contains proposal-stage rules plus general midpoint/final guidance. No separate final-submission rubric, later announcement, instructor feedback or final deadline was provided. Their existence or completion cannot be inferred.

Sources reviewed: the instructor-provided Problem Set 06 PDF and the student proposal PDF (not bundled here). Source documents are evidence, not permission to perform external submissions. The assignment explicitly states that the proposal is not a contract and projects may change.

## Instructor requirements

| Requirement | Evidence / status | Remaining action |
|---|---|---|
| Individual project; student understands submitted system | Architecture is inspectable; AI assistance now disclosed in README. Understanding cannot be verified from files. | Student should explain scoring, constraints, rebuilds, route optimization, fallback logic and limitations independently. |
| Clearly cite external material and distinguish created/reused work | README now names datasets, APIs, libraries, infrastructure and substantial Codex assistance. | Check data redistribution terms; provide exact model ID used in final experiments; identify any further borrowed assets/code. |
| Proposal: slide PDF at username/proposal.pdf | Local `diaomj668/proposal.pdf` exists and contains five core slides covering the requested topics. | Actual on-time PR to onexi/ps06 and five-minute class presentation are not verified. The due date stated in this file was October 29, 2026, 9 a.m. Eastern. |
| Midpoint: working repository and concise progress demonstration | Working deployment/source copy exists; original README was a midpoint description. | Actual submitted repository, midpoint presentation and instructor feedback are unverified. |
| Final: completed, polished project | Core planner, checker, chat, maps and constraints work in tested scenarios. | Remaining reliability/UX issues should be fixed or explicitly scoped out; temporary tunnel is not durable hosting. |
| Final: GitHub source and all build/run files | Current source and metadata exist locally in the output/deployment copy. | **Not verified in GitHub.** Sync current code/tests/docs and supply data acquisition or permitted dataset packaging. Do not assume changes made here updated the Desktop checkout or GitHub. |
| README: behavior, installation, architecture, external resources | Rewritten in English to reflect current implementation and real limitations. | Test the instructions from a clean checkout with fresh credentials and dataset availability. |
| Final: concise demonstration/presentation | Existing PDF is the proposal, not a final demo. `tuesday_overview.pptx` is a one-slide overview. | Prepare a final presentation showing distinctive behavior, evidence and limitations. No final length/deadline is stated in the supplied pages. |
| Reliability claims supported by testing | Automated tests and offline 20-request script exist; historical results were stale and are being regenerated. | Add negative/infeasible cases, multi-day regression scenarios, UI checks and clearly separated live API checks. Do not claim broad live reliability based only on offline checks. |

## Student proposal commitments (not mandatory instructor feature specifications)

| Proposal claim | Current status | Honest interpretation / action |
|---|---|---|
| One-day planner with hours, travel and budget checks | Implemented | Budget checks verify stated price assumptions, not actual prices. |
| Every recommended stop links to a real record | Implemented | Stops come from local metadata and include dataset IDs/record links. |
| Build/check/rebuild after a failed check | Implemented | Python orchestration; not the same as interactive replanning after a user reports a closure. |
| Multi-day planning | Implemented with limits | Independent days, no reused records; same daily start, no joint area allocation or lodging model. |
| Taste ranking using review text and 10-core reviews | **Not implemented** | Current ranking uses review counts, ratings, categories and travel distance. It does not read review text. Either implement a bounded review-text feature or explicitly declare a scope change. |
| Rebuild the remaining day when a stop closes | **Not implemented** | No UI/API preserving completed stops/current position while replacing a future stop. Implement or declare deferred. |
| Twenty requests on planner and plain-chatbot baseline | **Only planner side exists** | Same-request chatbot experiment and comparative results are absent. This is the largest missing piece of the proposal's evaluation plan. |
| Zero time clashes | Tested on offline sample requests | Distinguish infeasible/no-plan requests from successful plans and add adversarial cases. |
| Zero made-up hours or prices | **Claim needs qualification** | Hours are checked against a historical record; dollar values are deliberately chosen estimates. Say “no unsupported factual prices presented; all estimates explicitly labelled,” not “all prices are data facts.” |
| Data count 87,588 after cleaning | Changed to 87,554 | Current cleaning removes 31 out-of-state and 10 coordinate-invalid records as well as 4,925 permanently closed ones. Explain changed rules instead of repeating the proposal count. |
| Python/pandas/Claude/OpenStreetMap | Revised architecture | pandas is not used; Google routing/maps were added. Explain this as an implementation choice. |

## English-only project check

Project-owned source, UI and submission documentation should be English. The prior Chinese deployment document and audit were moved out of deliverables into the working archive and replaced by English documentation. Claude's system prompt now requests English replies and notes for any input language. User-entered messages and original business proper names are source/user content, not translated interface text. User-entered text can still appear in place labels and map content. Third-party Google map localization is determined by its loader/browser settings unless explicitly fixed.

## Prioritized completion plan

1. Verify the actual final assignment/announcement and instructor feedback; this audit cannot establish requirements that were not supplied.
2. Make the final repository reproducible and synchronized with the running version. Run clean-install instructions; ensure secrets are excluded.
3. Finish the promised same-20-request chatbot comparison, preserving prompts, model IDs, outputs, evaluation rules, failure cases and limitations. Do not fabricate results.
4. Resolve the two proposal extensions: implement review-text personalization and remaining-day replanning, or document a justified reduced scope. The instructor's proposal-not-a-contract statement supports honest revisions.
5. Prepare an English final demo: grounded input, city-constrained plan, meal/time constraints, map-card interaction, checker evidence, a failure case and limitations.
6. Improve long-term hosting and global paid-API limits if the demonstration must remain available without the student's laptop.

## Current technical limitations relevant to grading

Local route improvement is bounded and not globally optimal; days are not jointly clustered. Interest mappings are incomplete. Meals are optional when Food is selected and cannot always fit the stop limit/budget. Opening hours are historical. Fixed price tiers and visit lengths are approximate. Address-text city checks are not administrative boundary geometry. The standard-library HTTP server and temporary local tunnel are demo infrastructure. These should be accurately described, not hidden behind a generic “checked” badge.
