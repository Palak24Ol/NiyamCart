# NiyamCart Execution Checklist

This is the operational tracker. A phase is not complete until every exit-gate item is checked.

## Phase 0 - Governance and project setup

- [x] Create BoundedCart folder.
- [x] Write master plan and scope lock.
- [x] Choose provisional primary LLM.
- [x] Create repository metadata and base README.
- [x] Confirm ownership and reuse permission for imported code/assets.
- [x] Review the existing local Kavach Saathi source without modifying it.
- [x] Produce a keep/modify/remove inventory by file/module.
- [x] Create concise `ADAPTATION.md`.
- [x] Scan imported material for secrets and personal data.
- [x] Confirm no irrelevant media or dependencies are imported.

## Phase 1 - Clean foundation

- [x] Import only the buyer-facing frontend shell.
- [x] Import only relevant backend infrastructure.
- [x] Remove seller, admin, delivery, return, review, voice, address, and image workflows.
- [x] Replace Kavach-specific names in active application code.
- [x] Add small purpose-built product catalogue.
- [x] Make frontend, backend, and database start locally.
- [x] Establish lint, unit-test, and build commands.
- [x] Verify clean setup instructions.

## Phase 2 - Money and payment safety

- [x] Delete raw card/CVV collection and synthetic capture shortcuts.
- [x] Convert all money fields and APIs to integer paise.
- [x] Add cart and order state machines.
- [x] Add database-level idempotency constraints.
- [x] Add order-creation idempotency key.
- [x] Add row lock or conditional finalisation update.
- [x] Test duplicate callback and webhook races.
- [x] Test invalid state regressions.

## Phase 3 - Machine-readable merchant

- [x] Define catalogue JSON Schema.
- [x] Define policy JSON Schema.
- [x] Create `merchant.yaml`.
- [x] Implement `/.well-known/agent-catalog.json`.
- [x] Implement `/.well-known/agent-policy.json`.
- [x] Add catalogue version and ETag.
- [x] Add compatibility tags.
- [x] Add allow/deny/escalate policy engine.
- [x] Add policy rule IDs and explanations.
- [x] Test catalogue and policy contracts.

## Phase 4 - Agent loop

- [x] Implement `search_catalog`.
- [x] Implement `get_product_details`.
- [x] Implement `find_compatible_addons`.
- [x] Implement `get_policy`.
- [x] Implement `propose_cart`.
- [x] Implement `escalate_to_human`.
- [x] Implement maximum eight-step loop.
- [x] Persist every turn and tool result.
- [x] Add step, revision, and spend budgets.
- [x] Add typed errors and one repair attempt.
- [x] Add safe abstention and degraded mode.
- [x] Add buyer- and catalogue-prompt-injection tests.
- [x] Prove there is no agent-callable payment/order function.

## Phase 5 - Cart approval

- [x] Re-price cart from authoritative product data.
- [x] Re-check inventory and compatibility.
- [x] Canonically serialise cart.
- [x] Generate SHA-256 cart hash.
- [x] Freeze cart for fifteen minutes.
- [x] Require explicit approval of exact hash.
- [x] Reject expired cart.
- [x] Reject mutated cart.
- [x] Reject unapproved cart.
- [x] Require re-approval after any change.

## Phase 6 - Razorpay

- [x] Create one Razorpay test order per approved cart.
- [x] Bind receipt/metadata to cart hash.
- [x] Open Razorpay Checkout.
- [x] Verify checkout signature.
- [x] Fetch payment from Razorpay.
- [x] Verify captured status.
- [x] Verify amount and currency.
- [x] Verify expected Razorpay order ID.
- [x] Route callback and webhook through one finaliser.
- [x] Deduplicate webhook event IDs.
- [x] Handle out-of-order events.
- [x] Demonstrate duplicate-order safety.

## Phase 7 - Frontend and audit

- [x] Add buyer-agent panel to reused frontend.
- [x] Show tool activity without exposing hidden reasoning.
- [x] Show grounded product recommendations.
- [x] Show policy refusal and rule ID.
- [x] Show frozen cart and exact approval.
- [x] Show checkout and verified payment state.
- [x] Show sequenced audit timeline.
- [x] Add audit verification endpoint.
- [x] Redact secrets and sensitive values.
- [x] Add accessible loading, error, and degraded states.

## Phase 8 - Evaluation and reliability

- [x] Declare success thresholds.
- [x] Create development tasks.
- [x] Create untouched held-out tasks.
- [x] Implement keyword baseline.
- [x] Implement single-shot LLM baseline.
- [x] Implement full-agent evaluation arm.
- [x] Add twelve-case adversarial suite.
- [x] Record exact model and prompt versions.
- [x] Report primary and secondary metrics.
- [x] Preserve failing transcripts.
- [x] Run unit, integration, property, and browser tests.
- [x] Test LLM outage, malformed output, timeout, and rate limit.

## Phase 9 - Optional WhatsApp handoff

- [x] Start only after Phases 0-8 are green.
- [x] Require explicit opt-in.
- [x] Send secure cart-review link, not financial approval.
- [x] Send confirmation only after backend verification.
- [ ] Use an approved/sandbox-compatible utility template.
- [x] Add notification idempotency.
- [x] Add feature flag and in-app fallback.
- [x] Verify core demo works with WhatsApp disabled.

## Phase 10 - Repository and submission

- [x] README opens with problem, thesis, and concise reuse disclosure.
- [x] `ADAPTATION.md` accurately identifies reused and new work.
- [x] `docs/architecture.md` exists and matches implementation.
- [x] Architecture diagram shows probabilistic/deterministic trust boundary.
- [x] Setup works on a clean machine.
- [x] CI is green.
- [x] Repository contains no secrets or personal data.
- [x] Repository contains no broken links.
- [x] Evaluation report is committed.
- [x] Limitations are explicit.
- [ ] Five-minute video is recorded and accessible.
- [ ] Demo has been rehearsed three times under five minutes.
- [ ] Submission form is reviewed before final submission.

## Final acceptance checklist

- [ ] One natural-language buyer request reaches one verified Razorpay test payment.
- [x] The agent selects tools dynamically and reacts to typed results.
- [x] The agent cannot cause a financial side effect.
- [x] Every rupee is represented as integer paise.
- [x] The buyer approves the exact cart that becomes the order.
- [x] Payment truth is independently reconciled.
- [x] Duplicate requests cannot create duplicate orders.
- [x] One unsafe request is refused with a real policy reason.
- [x] One provider failure is handled without fabrication.
- [x] Audit records reproduce the workflow without relying on an LLM explanation.
- [x] Metrics are calculated on held-out tasks and limitations are stated honestly.
