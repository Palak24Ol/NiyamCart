# NiyamCart

**AI shopping, within your rules.**

## Problem

AI shopping becomes unsafe when a probabilistic model can invent product facts, change prices, or
act as if it approved and verified a payment. Merchants also need machine-readable catalogues and
policies before an AI buyer can transact with them reliably.

## Thesis

NiyamCart is a bounded AI shopping agent for Razorpay AI Buildathon Track 1. The model may search,
compare, explain, and propose through six typed tools. Deterministic server code owns prices,
inventory, policy, the exact cart hash, human approval, order creation, Razorpay test reconciliation,
and the audit trail.

## Reuse disclosure

The buyer-storefront concepts, authorized 500-product seed data, and primary product images were
selectively adapted from the team’s earlier Kavach Saathi project. No source file was copied
wholesale, and unrelated agents/workflows, old branding, user data, and credentials were excluded.
The bounded agent loop, machine contracts, policy engine, cart-hash approval, hardened Razorpay
flow, verifiable audit, evaluation harness, and safe handoff are new Buildathon work. Exact provenance
is documented in `ADAPTATION.md`.

## Current checkpoint

The clean frontend/backend foundation is implemented with:

- Searchable and filterable 500-product catalogue across 10 categories.
- 500 locally hosted, compressed primary product images.
- Integer-paise product data and Indian currency formatting.
- Interactive cart with quantities and totals.
- Live Niyam assistant panel with explained, catalogue-grounded recommendations.
- Buyer-gated “Complete the look” cross-sells with compatibility reasons and explicit add controls.
- Visible baseline/suggested totals, potential AOV uplift, and accepted/rejected upsell evidence.
- Proposed-cart handoff and a visible human-approval boundary.
- Responsive desktop and mobile layouts.
- FastAPI health and catalogue endpoints backed by SQLAlchemy.
- SQLite for zero-config local development; `DATABASE_URL` remains configurable.
- Authoritatively priced carts with a deterministic 15-minute freeze.
- Persisted add-on compatibility claims revalidated before freeze, approval, and order creation.
- SHA-256 binding between the exact cart, human approval, and order.
- Stored cart hashes are recomputed at approval and order time to reject any mutation.
- Database-enforced cart/order states and idempotency constraints.
- Duplicate-safe payment evidence finalisation with amount and currency verification.
- Razorpay test-order creation bound to the internal order, receipt, and exact cart hash.
- Standard Checkout with a separate human approval action and server-side signature verification.
- Callback and raw-body-verified webhook reconciliation through one payment finaliser.
- Bounded Groq/OpenAI tool loop with six strict merchant tools.
- Separate judge-facing Trust & Audit drawer with redacted, hash-chained agent, cart, and order evidence.
- One-click autonomous-payment refusal demo with the exact policy rule and zero commerce side effects.
- Post-payment receipt with order, amount, Razorpay test-payment, timestamp, and WhatsApp state.
- Deterministic 100-point product match breakdowns with catalogue evidence per component.
- Expiring SHA-256 intent mandates binding budget, stock, add-on, and always-ask payment rules.
- Conversational saved/new/current-location delivery flow before final cart locking, with explicit
  consent before OpenStreetMap reverse geocoding and manual confirmation of the returned address.
- Merchant-approved Razorpay test-offer ranking; previews are disabled until an Offer ID is set.
- Self-healing cart rescue that shows replacements, revokes prior approval, and requires reapproval.
- Causal Growth Ledger separating exposure, rejection, acceptance, and realised test uplift.
- Functional login and sign-up with scrypt password hashing and HttpOnly cookie sessions.
- Protected My Orders and Profile pages with account-scoped browser storage for MVP preferences and receipts.
- Eight-step, two-revision, and per-session model-cost limits.
- Repair-once tool validation plus deterministic degraded mode when the model is unavailable.
- 99 automated tests spanning unit, integration, randomized properties, reliability, and races.

The frontend calls the bounded agent API directly. Shopper chat shows grounded products, policy
refusals, and safe degraded states. A separate Trust & Audit drawer shows typed tool activity and
hash-chain verification for judges without exposing hidden model reasoning.

## Run locally

Requirements: Node.js 20 or newer and Python 3.11 or newer.

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

Create and start the backend in a second terminal:

```bash
python -m venv .venv
python -m pip install -r backend/requirements-dev.txt
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

Open `http://localhost:8000/docs` for the local API explorer.

Login and sign-up are available at `http://localhost:3000/auth`. Development uses an HttpOnly,
SameSite cookie; set `AUTH_COOKIE_SECURE=true` behind production HTTPS. Passwords are stored only as
salted scrypt hashes. Profile preferences and verified order receipts remain account-scoped in the
current browser for this MVP and are not sent to the shopping agent.

## Deterministic commerce flow

1. `POST /api/carts` reprices requested products from authoritative catalogue data.
2. `POST /api/carts/{id}/freeze` rechecks price and stock, then creates a 15-minute SHA-256 cart hash.
3. `POST /api/carts/{id}/approve` accepts only the exact, unexpired hash.
4. `POST /api/orders` accepts only an approved cart and requires an idempotency key.
5. Payment evidence is finalised internally only after signature, capture, provider order, amount, and currency checks.

The public API exposes no raw-card or CVV fields. NiyamCart accepts only `rzp_test_` credentials.
Checkout callback data is never accepted as payment truth by itself: the backend fetches the payment
from Razorpay and matches captured status, amount, currency, and the server-stored provider order ID.

## Razorpay test-mode setup

Set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET` in your local
environment. Use only keys generated while the Razorpay Dashboard is in Test Mode. Configure the
test webhook URL as `POST /api/payments/razorpay/webhook` and enable `payment.captured`,
`payment.failed`, and `order.paid`.

The browser loads Razorpay Standard Checkout only after the buyer first locks the cart, reviews its
authoritative total and SHA-256 hash, and then clicks the separate exact-approval button. The secret
keys never enter the browser; only the public test key ID is returned in the checkout configuration.

## Agent-readable merchant

NiyamCart publishes stable machine contracts for AI buyers:

- `GET /.well-known/agent-catalog.json` — all 500 products with integer-paise prices, availability, attributes, compatibility tags, grounded complements, policy references, catalogue version, and ETag.
- `GET /.well-known/agent-policy.json` — seven ordered allow/deny/escalate rules with IDs and explanations.
- `POST /api/policy/evaluate` — deterministic evaluation of a proposed commerce action.
- `merchant.yaml` — merchant identity, endpoints, limits, payment boundary, and the exact six supported agent actions.

Both well-known endpoints support conditional requests through `If-None-Match` and return `304 Not Modified` when unchanged. Their JSON Schemas live in `backend/schemas/`.

## Bounded agent API

- `POST /api/agent/sessions` runs a new request through at most eight model turns.
- `POST /api/agent/sessions/{id}/messages` allows at most two buyer revisions.
- `GET /api/agent/sessions/{id}/events` returns the reproducible public audit timeline.
- `GET /api/audit/{scope}/{id}` recomputes and verifies the hash chain for an agent session, cart,
  or order.

Set `AI_PROVIDER=groq`, `GROQ_API_KEY`, and `GROQ_MODEL=openai/gpt-oss-20b` to use the
Groq-compatible live agent. OpenAI remains available through `AI_PROVIDER=openai`,
`OPENAI_API_KEY`, and `OPENAI_MODEL`. Without the selected provider key—or during a provider
failure—the endpoint falls back to deterministic catalog search, labels the result as degraded,
and never fabricates a cart. Model calls are additionally bounded by the configured step and cost
limits.

The only model-callable tools are catalog search, product details, compatible add-ons, policy
lookup, proposed-cart creation, and human escalation. Order creation, approval, checkout, and
payment are intentionally absent.

## Multilingual voice shopping

Niyam accepts typed or spoken shopping requests in 11 Indian languages. Sarvam handles speech
recognition, language detection, translation, and answer speech; the bounded commerce agent still
runs the same six catalogue and policy tools against an English canonical query. The visible answer
is returned in the shopper's detected language, while product cards retain authoritative catalogue
names, prices, stock, and add-to-cart actions.

Set `SARVAM_VOICE_ENABLED=true` and `SARVAM_API_KEY` in `.env`. Optional defaults are
`SARVAM_STT_MODEL=saaras:v3`, `SARVAM_TTS_MODEL=bulbul:v3`, and
`SARVAM_TTS_SPEAKER=shubh`. The key is server-only. Voice recordings are capped in the browser at
25 seconds and are sent directly to Sarvam for processing; Niyam does not save the audio.

## Evaluation

NiyamCart includes versioned development, held-out, and 12-case adversarial splits plus keyword,
single-shot, full-agent, and production-degraded evaluation arms. The offline report records 100%
held-out task success and a 0% unsafe-action rate for both measured offline arms. Live single-shot
and full-agent measurements are explicitly marked not run because no API credential was configured;
the runner never fabricates missing results.

See `docs/evaluation-plan.md`, `docs/evaluation-report.md`, and
`backend/evals/results/offline-report.json`. A live run is always explicit and uses the configured
provider:

```bash
python -m scripts.run_evaluation --split heldout --live --output backend/evals/results/live-report.json
```

## Optional WhatsApp handoff

The cart can send a signed, review-only WhatsApp message after explicit opt-in and exact destination
confirmation. It is feature flagged, idempotent, and cannot approve or pay. The raw destination is
used only for the provider call and is not persisted; audit records contain a keyed fingerprint.
A payment confirmation is gated on independently verified Razorpay test payment evidence. During
an active Twilio Sandbox 24-hour session, the sender uses a free-form message body. Approved Content
SIDs can be supplied later for production-style template delivery. See `docs/whatsapp-handoff.md`.

## Verify

```bash
npm run lint
npm run typecheck
npm run build
npm audit --omit=dev
python -m ruff check backend scripts
python -m pytest backend/tests -q
python scripts/security_check.py
python scripts/check_links.py
```

## Project records

- `MASTER_PLAN.md` — product, architecture, phases, and exit gates.
- `CHECKLIST.md` — live execution status.
- `ADAPTATION.md` — selective reuse and provenance record.
- `docs/SOURCE_AUDIT.md` — source review and exclusions.
- `docs/DECISIONS.md` — important product and technical decisions.
- `docs/architecture.md` — implemented trust boundary, components, states, and failures.
- `docs/evaluation-report.md` — measured results and explicitly unrun live arms.
- `docs/limitations.md` — honest MVP and deployment constraints.
- `docs/demo-script.md` — timed five-minute demonstration and rehearsal record.

## Safety boundary

The model will never receive tools that create orders, capture payments, or verify payments. An approved exact cart is handed to deterministic backend code, and payment uses Razorpay test mode.
