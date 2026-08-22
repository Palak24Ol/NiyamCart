# BoundedCart Execution Checklist

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
- [ ] Import only relevant backend infrastructure.
- [x] Remove seller, admin, delivery, return, review, voice, address, and image workflows.
- [x] Replace Kavach-specific names in active application code.
- [x] Add small purpose-built product catalogue.
- [ ] Make frontend, backend, and database start locally.
- [ ] Establish lint, unit-test, and build commands.
- [ ] Verify clean setup instructions.

## Phase 2 - Money and payment safety

- [ ] Delete raw card/CVV collection and synthetic capture shortcuts.
- [ ] Convert all money fields and APIs to integer paise.
- [ ] Add cart and order state machines.
- [ ] Add database-level idempotency constraints.
- [ ] Add order-creation idempotency key.
- [ ] Add row lock or conditional finalisation update.
- [ ] Test duplicate callback and webhook races.
- [ ] Test invalid state regressions.

## Phase 3 - Machine-readable merchant

- [ ] Define catalogue JSON Schema.
- [ ] Define policy JSON Schema.
- [ ] Create `merchant.yaml`.
- [ ] Implement `/.well-known/agent-catalog.json`.
- [ ] Implement `/.well-known/agent-policy.json`.
- [ ] Add catalogue version and ETag.
- [ ] Add compatibility tags.
- [ ] Add allow/deny/escalate policy engine.
- [ ] Add policy rule IDs and explanations.
- [ ] Test catalogue and policy contracts.

## Phase 4 - Agent loop

- [ ] Implement `search_catalog`.
- [ ] Implement `get_product_details`.
- [ ] Implement `find_compatible_addons`.
- [ ] Implement `get_policy`.
- [ ] Implement `propose_cart`.
- [ ] Implement `escalate_to_human`.
- [ ] Implement maximum eight-step loop.
- [ ] Persist every turn and tool result.
- [ ] Add step, revision, and spend budgets.
- [ ] Add typed errors and one repair attempt.
- [ ] Add safe abstention and degraded mode.
- [ ] Add buyer- and catalogue-prompt-injection tests.
- [ ] Prove there is no agent-callable payment/order function.

## Phase 5 - Cart approval

- [ ] Re-price cart from authoritative product data.
- [ ] Re-check inventory and compatibility.
- [ ] Canonically serialise cart.
- [ ] Generate SHA-256 cart hash.
- [ ] Freeze cart for fifteen minutes.
- [ ] Require explicit approval of exact hash.
- [ ] Reject expired cart.
- [ ] Reject mutated cart.
- [ ] Reject unapproved cart.
- [ ] Require re-approval after any change.

## Phase 6 - Razorpay

- [ ] Create one Razorpay test order per approved cart.
- [ ] Bind receipt/metadata to cart hash.
- [ ] Open Razorpay Checkout.
- [ ] Verify checkout signature.
- [ ] Fetch payment from Razorpay.
- [ ] Verify captured status.
- [ ] Verify amount and currency.
- [ ] Verify expected Razorpay order ID.
- [ ] Route callback and webhook through one finaliser.
- [ ] Deduplicate webhook event IDs.
- [ ] Handle out-of-order events.
- [ ] Demonstrate duplicate-order safety.

## Phase 7 - Frontend and audit

- [ ] Add buyer-agent panel to reused frontend.
- [ ] Show tool activity without exposing hidden reasoning.
- [ ] Show grounded product recommendations.
- [ ] Show policy refusal and rule ID.
- [ ] Show frozen cart and exact approval.
- [ ] Show checkout and verified payment state.
- [ ] Show sequenced audit timeline.
- [ ] Add audit verification endpoint.
- [ ] Redact secrets and sensitive values.
- [ ] Add accessible loading, error, and degraded states.

## Phase 8 - Evaluation and reliability

- [ ] Declare success thresholds.
- [ ] Create development tasks.
- [ ] Create untouched held-out tasks.
- [ ] Implement keyword baseline.
- [ ] Implement single-shot LLM baseline.
- [ ] Implement full-agent evaluation arm.
- [ ] Add twelve-case adversarial suite.
- [ ] Record exact model and prompt versions.
- [ ] Report primary and secondary metrics.
- [ ] Preserve failing transcripts.
- [ ] Run unit, integration, property, and browser tests.
- [ ] Test LLM outage, malformed output, timeout, and rate limit.

## Phase 9 - Optional WhatsApp handoff

- [ ] Start only after Phases 0-8 are green.
- [ ] Require explicit opt-in.
- [ ] Send secure cart-review link, not financial approval.
- [ ] Send confirmation only after backend verification.
- [ ] Use an approved/sandbox-compatible utility template.
- [ ] Add notification idempotency.
- [ ] Add feature flag and in-app fallback.
- [ ] Verify core demo works with WhatsApp disabled.

## Phase 10 - Repository and submission

- [ ] README opens with problem, thesis, and concise reuse disclosure.
- [ ] `ADAPTATION.md` accurately identifies reused and new work.
- [ ] `docs/architecture.md` exists and matches implementation.
- [ ] Architecture diagram shows probabilistic/deterministic trust boundary.
- [ ] Setup works on a clean machine.
- [ ] CI is green.
- [ ] Repository contains no secrets or personal data.
- [ ] Repository contains no broken links.
- [ ] Evaluation report is committed.
- [ ] Limitations are explicit.
- [ ] Five-minute video is recorded and accessible.
- [ ] Demo has been rehearsed three times under five minutes.
- [ ] Submission form is reviewed before final submission.

## Final acceptance checklist

- [ ] One natural-language buyer request reaches one verified Razorpay test payment.
- [ ] The agent selects tools dynamically and reacts to typed results.
- [ ] The agent cannot cause a financial side effect.
- [ ] Every rupee is represented as integer paise.
- [ ] The buyer approves the exact cart that becomes the order.
- [ ] Payment truth is independently reconciled.
- [ ] Duplicate requests cannot create duplicate orders.
- [ ] One unsafe request is refused with a real policy reason.
- [ ] One provider failure is handled without fabrication.
- [ ] Audit records reproduce the workflow without relying on an LLM explanation.
- [ ] Metrics are calculated on held-out tasks and limitations are stated honestly.
