# Kavach Saathi Source Audit

Audit date: 2026-08-22
Source location: `C:\Kavach-Saathi\kavach-saathi-main`
Source commit inspected: `895208eb9b1f465ec23e1d6770b0bd6b7b669c5f`
Source handling rule: read-only; do not change its Git configuration, files, or working tree.

## Repository state

- The source has two configured remotes, `origin` and `manya`.
- Git history contains contributions attributed to Palak Jaiswal, Manya Gupta, and `manya1632`.
- The working tree contains numerous untracked local files.
- No root `LICENSE`, `COPYING`, or `NOTICE` file was found.
- `web/ATTRIBUTION.md` says an external Meesho clone was used as a product-flow reference, with local source code and assets claimed as independently written.
- A local `.env` exists and contains populated configuration fields. Values were not copied or recorded.

## Security findings that block whole-repository copying

1. The local `.env` must never be imported or committed.
2. `commerce_api.py` contains a demo endpoint that accepts card number, expiry, and CVV and marks a synthetic payment as successful.
3. `Storefront.jsx` contains the matching raw-card form and caller.
4. Monetary database fields use floating-point columns.
5. Existing payment verification lacks server-side payment-fetch reconciliation.
6. Order creation lacks a Buildathon-grade cart-hash idempotency contract.
7. Callback and webhook finalisation require a single concurrency-safe finaliser.
8. Public-source contact details appear in active application files and must not be imported.

## Frontend inventory

### Reuse or extract selectively

| Source | Decision | BoundedCart use | Required changes |
|---|---|---|---|
| `web/app/layout.js` | Modify | Root layout | New metadata and branding |
| `web/app/page.js` | Modify | Buyer application entry | Load new BoundedCart experience |
| `web/app/globals.css` | Modify | Visual tokens and responsive base | Remove unrelated role/workflow styles |
| `web/app/agent-api/[...path]/route.js` | Modify | Server-side API proxy | New route names, safer error handling |
| `web/lib/api.js` | Rewrite from pattern | Typed client and buyer auth | Remove seller/delivery/admin tokens and legacy endpoints |
| `ProductCard` from `Storefront.jsx` | Extract and rewrite | Catalogue result card | Integer-paise display and new product schema |
| `CartDrawer` from `Storefront.jsx` | Extract and rewrite | Proposed/frozen cart display | No direct mutable legacy cart flow |
| `CheckoutDrawer` from `Storefront.jsx` | Extract and rewrite | Approval and Razorpay handoff | Remove COD, address guardian, WhatsApp delivery, raw card dialog |
| `AuthModal` from `Storefront.jsx` | Extract and simplify | Buyer authentication | Email-only demo-safe flow |
| Buyer Playwright journey | Rewrite | Core e2e test | New agent-to-payment workflow |

### Do not import

- `SellerPortal.jsx`
- `DeliveryPortal.jsx`
- `AdminConsole.jsx`
- `Support.jsx`
- Seller, delivery, admin, return, wishlist, address, and KYC routes
- Return-media drawers and recording UI
- Voice Q&A and multilingual controls
- `CardPaymentDialog` and all card/CVV state
- COD and WhatsApp-delivery-confirmation controls

### Frontend architecture decision

`Storefront.jsx` is more than 3,000 lines and mixes unrelated roles and workflows. It will not be copied wholesale. Relevant visual behavior will be extracted into small BoundedCart components with clear ownership and tests.

## Backend inventory

### Reuse or adapt selectively

| Source | Decision | BoundedCart use | Required changes |
|---|---|---|---|
| `app.py` | Rewrite from pattern | FastAPI application composition | Only BoundedCart routers and middleware |
| `config.py` | Rewrite from pattern | Typed configuration | Minimal keys; OpenAI + Razorpay only for MVP |
| `auth.py` | Review and adapt | Buyer authentication | Remove unused role branches and OTP providers |
| `db/base.py` | Adapt | SQLAlchemy base/session | New package and database names |
| Product/order/payment model shapes | Rewrite | Core commerce schema | Integer paise, cart hash, approval, idempotency, state constraints |
| `providers/razorpay_provider.py` | Rewrite | Razorpay adapter | Paise input, timeouts, fetch/reconcile, typed errors |
| Webhook HMAC and event-dedupe pattern | Adapt | Webhook safety | One locked finaliser and ordering guards |
| `redis_client.py` | Simplify | Idempotency/session cache | Drop Streams and worker clients initially |
| `_claim_once` pattern | Reimplement | Short-lived operation claims | Add database uniqueness as source of truth |
| `providers/reasoning.py` | Rewrite interface | OpenAI Responses provider | Function calling, exact usage/cost capture, safe unavailable state |
| `agent_logging.py` | Rewrite | Audit events | Sequence, actor, decision, rule IDs, cart hash, redaction, optional hash chain |
| Test fixtures and test style | Adapt | Test foundation | New models, routes, agent loop, and payment state machine |
| Docker patterns | Adapt | Local setup | Smaller dependency and service footprint |

### Do not import

- All existing files under `agents/`
- Existing `orchestration/graph.py`
- Delivery, seller, admin, specs, trust, media, and operational APIs
- Vision, image-generation, OCR, maps, DigiLocker, voice, WhatsApp, Pinecone, and return providers
- Event worker/Redis Streams unless a measured need appears
- Existing migration chain; create one clean BoundedCart baseline migration
- Existing seeded apparel catalogue and media

## Secrets and personal-data policy

- Never copy the source `.env`.
- Generate a new safe `.env.example` containing empty placeholders only.
- Run secret scanning before every public commit.
- Do not import hard-coded phone numbers, email addresses, provider SIDs, tokens, API keys, or personal media.
- Razorpay, OpenAI, and optional Twilio credentials remain server-side and uncommitted.

## Permission gate

Selective reuse can begin only after the user confirms that they own the relevant source or have permission from all contributors to reuse it in BoundedCart. Multiple Git authors and remotes make sole ownership impossible to infer from the filesystem alone.

