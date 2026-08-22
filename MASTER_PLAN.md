# BoundedCart Master Plan

Status: planning and scope lock
Track: Razorpay AI Buildathon - Track 1, AI Growth & Agentic Commerce
Primary goal: make one merchant safely transactable by an AI buyer end to end in Razorpay test mode.

## 1. Product thesis

BoundedCart is a policy-controlled AI shopping agent. A merchant publishes a machine-readable catalogue and policy. The agent can search, inspect, reason, and propose a cart through six typed tools. Deterministic code owns prices, inventory, approval, order creation, payment verification, finalisation, and audit writes.

The trust boundary is:

```text
AI proposes -> deterministic code validates -> buyer approves -> backend executes -> Razorpay processes -> backend verifies
```

## 2. Official Track 1 bar translated into engineering requirements

- Explainable: every recommendation and refusal references catalogue evidence or a policy rule.
- Bounded: hard step, quantity, spend, revision, timeout, and retry limits are enforced in code.
- Gated: no order can be created without explicit approval of the exact frozen cart.
- Audited: every tool call and financial state transition is appended to a verifiable audit timeline.
- Failure-aware: duplicate order submission and LLM outage are demonstrated safely.
- End to end: a buyer request reaches a verified Razorpay test-mode payment and final order state.

## 3. Scope lock

### Must build

1. One merchant and one curated catalogue.
2. One buyer-facing experience.
3. One genuine tool-selecting agent loop, maximum eight steps.
4. Six typed, read/propose-only agent tools.
5. Machine-readable catalogue and policy endpoints.
6. Deterministic policy engine.
7. Frozen cart, cart hash, expiry, and explicit approval.
8. Idempotent Razorpay test-order creation.
9. Signature verification plus server-side payment reconciliation.
10. Single safe order finaliser.
11. Append-only audit timeline.
12. Duplicate-order and LLM-outage demonstrations.
13. Controlled evaluation with baselines.
14. Public setup, architecture, limitations, and provenance documentation.

### Stretch only after the MVP is green

- WhatsApp cart handoff through a secure link.
- Verified post-payment WhatsApp notification.
- A small, explicitly synthetic upsell experiment.

### Explicitly excluded

- Multiple agents or multiple merchants.
- Voice commerce, WhatsApp chat purchasing, campaigns, or recovery spam.
- UAP, ACP, AP2, or x402 implementation.
- Refunds, payouts, real money, COD, or autonomous payment retries.
- Return, delivery, address, trust, review, or image-generation workflows.
- Merchant configuration dashboard; use version-controlled configuration.
- Vector database for a small catalogue.
- AI-created prices, discounts, compatibility, payment state, or audit facts.

## 4. Agent design

The agent can call only:

1. `search_catalog`
2. `get_product_details`
3. `find_compatible_addons`
4. `get_policy`
5. `propose_cart`
6. `escalate_to_human`

No tool can create an order, initiate payment, fetch payment truth, retry payment, approve a cart, or finalise an order.

Agent limits:

- Maximum eight steps.
- Maximum two cart revisions.
- Maximum one add-on proposal.
- Session spend cap.
- Temperature/reasoning configuration pinned for evaluation.
- Typed tool arguments and typed tool errors.
- One structured-output repair attempt, then safe degradation.
- Forced terminal state: proposed, refused, escalated, or failed.

## 5. Deterministic commerce design

### Catalogue

- Product IDs, names, descriptions, categories, attributes, inventory, price in paise, and compatibility tags.
- Published at `/.well-known/agent-catalog.json`.
- Versioned and ETagged.

### Policy

- Stored in `merchant.yaml`.
- Published at `/.well-known/agent-policy.json`.
- Returns `allow`, `deny`, or `escalate` with rule IDs and human-readable reasons.
- Non-negotiable invariants remain hard-coded and tested.

### Cart approval

- Re-price and re-check inventory at proposal time.
- Canonically serialise the cart.
- Generate a SHA-256 `cart_hash`.
- Freeze the cart for 15 minutes.
- Buyer approves the exact hash.
- Any change invalidates approval and requires a new approval.

### Payment

- Store every monetary value as integer paise.
- Create an internal order idempotently from the approved cart hash.
- Create one Razorpay test order.
- Verify the checkout signature.
- Fetch payment state from Razorpay.
- Match captured status, amount, currency, and order ID.
- Route callback and webhook processing through one locked finaliser.
- Deduplicate webhook events and ignore invalid state regressions.

## 6. Reuse strategy

Only code we own or are authorised to reuse may be imported.

### Reuse candidates from Kavach Saathi

- Buyer authentication UI.
- Navigation and responsive shell.
- Catalogue, product-card, product-detail, cart, checkout, and order-result components.
- Next.js API proxy pattern.
- FastAPI application/config/database foundation.
- Product, order, and payment model shapes after safety changes.
- Razorpay client, signature verification, and webhook deduplication.
- Redis idempotency helper.
- LLM provider abstraction and honest degraded mode.
- Test and Docker foundations.

### Do not import

- Existing eight-agent orchestration.
- Return, delivery, address, review, voice, WhatsApp, image, and trust modules.
- Large old media collections.
- Old demo payment endpoint.
- Secrets, personal contact details, credentials, or unrelated seeded records.

### Provenance rule

Reusing our own prior work is permitted engineering reuse, but it must not be presented as newly written from scratch. The repository will include a concise adaptation note identifying reused foundations and new Buildathon work. Commit history and documentation must be truthful.

## 7. LLM choice

### Primary

`gpt-5.6-luna` through the OpenAI Responses API.

Why:

- Supports function calling and structured outputs.
- Low cost and suitable latency for a constrained six-tool loop.
- Large context is unnecessary but leaves headroom for catalogue evidence and policy context.

### Upgrade path

`gpt-5.6-terra` if the held-out tool-selection evaluation shows that Luna misses the target quality threshold.

### Failure path

No hidden second model makes financial decisions. If the model is unavailable, the agent enters a clearly labelled degraded state and does not create an order. A deterministic keyword/search fallback may display products but cannot impersonate the agent or purchase.

### Implementation rule

Model and snapshot/alias are configured by environment variables. Evaluation records the exact model, prompt version, tool-schema version, and run parameters.

## 8. Delivery phases

### Phase 0 - Governance and clean-room import

Deliverables:

- New project folder and repository.
- Master plan, checklist, adaptation note, and decision log.
- Ownership/license check for every imported component and asset.
- Selective import inventory.
- Secret and personal-data scan.

Exit gate:

- We can name the origin and purpose of every imported module.
- No unrelated feature is present.
- No sensitive data is committed.

### Phase 1 - Minimal clean application

Deliverables:

- Reused buyer UI shell running locally.
- FastAPI health endpoint.
- PostgreSQL migrations.
- Small curated catalogue.
- One-command local setup.

Exit gate:

- Fresh setup works.
- Catalogue renders.
- Tests and lint run.

### Phase 2 - Financial data safety

Deliverables:

- Integer-paise migration.
- No raw card/CVV collection.
- Removed synthetic payment-capture shortcut.
- Order/cart state machines.
- Idempotency primitives.

Exit gate:

- No floating-point money exists.
- Duplicate requests cannot create duplicate internal orders.

### Phase 3 - Catalogue and policy contracts

Deliverables:

- `merchant.yaml`.
- Agent catalogue endpoint.
- Agent policy endpoint.
- Pure policy engine with rule IDs.
- Compatibility and inventory checks.

Exit gate:

- Policy tests cover allow, deny, and escalate.
- Catalogue and policy schemas validate.

### Phase 4 - Bounded agent

Deliverables:

- Six tool schemas and repository implementations.
- Tool-calling loop with persisted transcript.
- Step/revision/spend limits.
- Typed errors, repair, abstention, escalation, and degraded mode.
- Prompt-injection boundary tests.

Exit gate:

- Agent uses at least two tools on representative tasks.
- Agent revises after a typed rejection.
- Agent cannot access any financial side-effect function.

### Phase 5 - Frozen cart and approval

Deliverables:

- Deterministic pricing and validation pipeline.
- Canonical cart serialisation and cart hash.
- Fifteen-minute expiry.
- Mandatory buyer approval state.
- Re-approval on any cart change.

Exit gate:

- Order creation rejects an unapproved, changed, or expired hash.

### Phase 6 - Razorpay end to end

Deliverables:

- Idempotent Razorpay test-order creation.
- Checkout integration.
- Signature verification.
- Payment fetch/reconciliation.
- Single locked finaliser.
- Webhook dedupe and ordering guards.

Exit gate:

- One approved cart produces one verified order.
- Callback/webhook races cannot double-finalise.

### Phase 7 - Audit and user experience

Deliverables:

- Sequenced append-only audit events.
- Optional hash chain and verification endpoint.
- Agent activity, policy refusal, approval, payment, and audit UI.
- Clear error and degraded states.

Exit gate:

- Every money-adjacent action is explainable from stored facts.
- Audit output contains no secrets or sensitive payment data.

### Phase 8 - Evaluation

Deliverables:

- Twenty to forty held-out tasks.
- Keyword baseline.
- Single-shot LLM baseline.
- Full bounded-agent arm.
- Adversarial suite.
- Machine-readable and README-ready reports.

Primary metrics:

- Constraint satisfaction.
- Hallucination rate.
- Policy-violation rate.
- Correct abstention.
- End-to-end completion.
- Cost and latency per completed task.

Secondary metrics:

- Tool-call validity.
- Mean tool calls.
- Duplicate orders created.
- Failure recovery rate.

Exit gate:

- Success criteria are declared before the final held-out run.
- Failing transcripts are retained, not hidden.

### Phase 9 - WhatsApp stretch

Deliverables:

- Explicit opt-in.
- Secure cart-handoff link.
- Verified post-payment utility notification.
- Idempotent notification delivery.
- Feature flag and in-app fallback.

Exit gate:

- Core checkout works with WhatsApp disabled.
- WhatsApp never approves, charges, verifies, or retries payment.

### Phase 10 - Submission

Deliverables:

- README with thesis, setup, architecture, real results, reuse disclosure, and limitations.
- Architecture document and decision records.
- Public evaluation fixtures and report.
- Green CI and fresh-machine setup test.
- Five-minute video with timed script.
- Backup local demonstration.

Exit gate:

- No broken links, secrets, personal data, dead routes, or misleading claims.
- Demo completes three times within five minutes.

## 9. Five-minute demo target

1. Thesis and concise prior-foundation disclosure.
2. Buyer request and genuine multi-tool agent run.
3. Frozen cart, exact approval, and Razorpay test checkout.
4. Verified payment and audit timeline.
5. Policy refusal or prompt-injection block.
6. Duplicate-order or LLM-outage recovery.
7. Three headline evaluation results and honest limitations.

## 10. Direction-control rules

Before adding any feature, answer:

1. Does it directly satisfy an official Track 1 requirement?
2. Does it improve the five-minute demonstration?
3. Can it be tested objectively before the deadline?
4. Does it preserve the trust boundary?
5. Can it be completed without delaying a must-have item?

If fewer than four answers are yes, the feature stays out.

