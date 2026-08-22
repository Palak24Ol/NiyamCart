# NiyamCart

**AI shopping, within your rules.**

NiyamCart is a bounded AI shopping agent for Razorpay AI Buildathon Track 1. It helps buyers discover products, understand recommendations, build a cart, and retain control of the final approval and payment.

## Current checkpoint

The clean frontend/backend foundation is implemented with:

- Searchable and filterable 500-product catalogue across 10 categories.
- 500 locally hosted, compressed primary product images.
- Integer-paise product data and Indian currency formatting.
- Interactive cart with quantities and totals.
- Niyam assistant panel with explained recommendations.
- Proposed-cart handoff and a visible human-approval boundary.
- Responsive desktop and mobile layouts.
- FastAPI health and catalogue endpoints backed by SQLAlchemy.
- SQLite for zero-config local development; `DATABASE_URL` remains configurable.
- Authoritatively priced carts with a deterministic 15-minute freeze.
- SHA-256 binding between the exact cart, human approval, and order.
- Database-enforced cart/order states and idempotency constraints.
- Duplicate-safe payment evidence finalisation with amount and currency verification.

The assistant response is intentionally simulated in this first frontend checkpoint. The bounded OpenAI tool loop and deterministic backend are built in later phases.

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

The public API exposes no raw-card or CVV fields. Razorpay API wiring is added in the dedicated integration phase; the state machine and verification boundary already exist.

## Agent-readable merchant

NiyamCart publishes stable machine contracts for AI buyers:

- `GET /.well-known/agent-catalog.json` — all 500 products with integer-paise prices, availability, attributes, compatibility tags, grounded complements, policy references, catalogue version, and ETag.
- `GET /.well-known/agent-policy.json` — seven ordered allow/deny/escalate rules with IDs and explanations.
- `POST /api/policy/evaluate` — deterministic evaluation of a proposed commerce action.
- `merchant.yaml` — merchant identity, endpoints, limits, payment boundary, and the exact six supported agent actions.

Both well-known endpoints support conditional requests through `If-None-Match` and return `304 Not Modified` when unchanged. Their JSON Schemas live in `backend/schemas/`.

## Verify

```bash
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
