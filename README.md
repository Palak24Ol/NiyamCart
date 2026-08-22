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
