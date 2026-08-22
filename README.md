# NiyamCart

**AI shopping, within your rules.**

NiyamCart is a bounded AI shopping agent for Razorpay AI Buildathon Track 1. It helps buyers discover products, understand recommendations, build a cart, and retain control of the final approval and payment.

## Current checkpoint

The clean frontend/backend foundation is implemented with:

- Searchable and filterable 500-product catalogue across 10 categories.
- 500 locally hosted, compressed primary product images.
- Integer-paise product data and Indian currency formatting.
- Interactive cart with quantities and totals.
- Live Niyam assistant panel with explained, catalogue-grounded recommendations.
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
- Bounded OpenAI Responses tool loop with six strict merchant tools.
- Redacted, hash-chained audit events with server-side tamper verification.
- Eight-step, two-revision, and per-session model-cost limits.
- Repair-once tool validation plus deterministic degraded mode when the model is unavailable.

The frontend calls the bounded agent API directly. It shows typed tool activity, grounded product
evidence, policy rule IDs, safe degraded states, and audit verification without exposing hidden
model reasoning.

## Run locally

Requirements: Node.js 20 or newer.

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

Set `OPENAI_API_KEY` to use the live Responses API. The default model is
`gpt-5.6-luna` at low reasoning effort. Without a key—or during a provider failure—the endpoint
falls back to deterministic catalog search, labels the result as degraded, and never fabricates a
cart. Model calls are additionally capped by `AGENT_MAX_COST_MICROUSD`.

The only model-callable tools are catalog search, product details, compatible add-ons, policy
lookup, proposed-cart creation, and human escalation. Order creation, approval, checkout, and
payment are intentionally absent.

## Verify

```bash
npm run lint
npm run typecheck
npm run build
npm audit --omit=dev
python -m ruff check backend scripts
python -m pytest
```

## Project records

- `MASTER_PLAN.md` — product, architecture, phases, and exit gates.
- `CHECKLIST.md` — live execution status.
- `ADAPTATION.md` — selective reuse and provenance record.
- `docs/SOURCE_AUDIT.md` — source review and exclusions.
- `docs/DECISIONS.md` — important product and technical decisions.

## Safety boundary

The model will never receive tools that create orders, capture payments, or verify payments. An approved exact cart is handed to deterministic backend code, and payment uses Razorpay test mode.
