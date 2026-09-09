# Persistent buyer journey

Open **My journey** (`/journey`) from the storefront or account navigation. The existing storefront,
voice shopping and exact-cart Razorpay test checkout remain available.

## Implemented flows

1. **Missions:** save a goal, up to four item requirements, delivered-total budget and optional
   deadline. The agent researches with the existing six tools. Deterministic catalogue search checks
   each requirement, excludes rejected products when memory is enabled, ranks candidates, and
   assembles up to three complete baskets. Missing budget/items produce clarification questions.
   Missions and conversation summaries are account-scoped and durable. Optimistic revisions reject
   stale edits; selecting the same basket reuses its cart.
2. **Memory:** server-backed profile and explicitly enabled size, brands, usual budget and rejected
   product preferences. Phone/email are not sent into mission research. Preferences can be cleared.
   Existing mission/audit history is retained. Size is advisory: the catalogue has no stock per size.
3. **Watches:** availability and maximum delivered-total conditions, expiry, in-app notification,
   a fresh proposed cart, pause/resume/check/stop. No emails or WhatsApp campaigns are sent.
4. **Delivery planning:** the full basket includes the merchant catalogue's delivery charge and
   conservative maximum arrival estimate. Budget and deadline are checked again when locking,
   approving and ordering. No carrier guarantee is claimed.
5. **Recovery:** buyer-enabled recovery tasks preserve quantity and spending limits, prepare a
   fresh cart when appropriate, and suggest alternatives for review when stock is missing.
   Compatibility bundles need a new mission review. Any existing unresolved order blocks replacement.
   My Orders can fetch Razorpay order payments, independently verify captured evidence, and reopen
   the **same** approved provider order only if no successful/unresolved attempt is found. An unknown
   or malformed provider response blocks retry. There is no autonomous charge or capture.
6. **Aftercare:** account-scoped backend order history, verified payment receipts, delivery timeline,
   estimate-overdue notifications, and a four-tool agent for tracking, return eligibility, receipts
   and support drafts. It uses the configured provider; without it, labelled deterministic routing
   works. Final answers use verified tool outcomes, never an invented model delivery/refund claim.
7. **Returns/exchanges:** verify paid order, delivered event and current catalogue return window;
   prepare an item-value estimate and replacement price difference; reconfirm stock/price/window
   on submission. Duplicate item claims are blocked. Cases enter a durable local merchant review
   queue, not a completed refund or shipment. Requests cover all purchased units of the selected SKU.
8. **Replenishment:** buyer chooses an interval. On its due date, prepare a fresh reviewable basket
   within the original total. A completed purchase schedules the next reminder; unreviewed baskets
   are not duplicated. Each reminder has an expiry and can be paused or stopped.
9. **External buyer:** `/.well-known/buyer-commerce.json` advertises a custom quote-only API.
   Authenticated buyers create a 15-minute bearer key, limited to 20 quotes with four products each.
   Keys can be revoked and never grant approval/payment authority. Requests are idempotent and
   return an account-protected handoff URL. This is **not** ACP/AP2/UAP/x402 certification.

## Worker and persistence

`JOURNEY_WORKER_ENABLED=true` (default) starts a 60-second poll loop with the backend. Conditions
are normally checked every 15 minutes; manual checks are available. Due times, expiry, leases,
retry counts and results live in SQL tables. The worker resumes overdue tasks after restart.
It does not run while the backend/computer is off. Run one catch-up cycle from the project root:

```powershell
$env:PYTHONPATH = "backend"
.venv\Scripts\python.exe -m app.journey_worker --once
```

Use the same database environment as the backend.
The lease claim and fenced execution prevent duplicate workers from preparing the same cart.
Proposal, task result and notification writes share one transaction. Five failures pause a task
for attention; earlier failures back off. Notifications are deduplicated and stored in-app.

New tables are additive and created by the existing startup schema initialization. No existing
table/column or user data is replaced. The old browser profile/receipt cache is retained but is not
treated as server payment evidence. Server order ownership derives from confirmed fulfilment or
an owned journey cart; legacy orders without either are not automatically assigned to an account.

## Merchant tracking integration

Set a random `MERCHANT_FULFILLMENT_WEBHOOK_SECRET` of at least 32 characters on the server.
Your merchant/carrier adapter sends `POST /api/fulfillment/merchant-webhook` with:

```json
{
  "event_id": "merchant-event-unique-0001",
  "order_id": "INTERNAL-ORDER-UUID",
  "status": "shipped",
  "detail": "Parcel handed to carrier",
  "occurred_at": "2026-09-05T10:00:00Z"
}
```

Headers: `X-Merchant-Timestamp` (Unix seconds), `X-Merchant-Signature` (hex HMAC-SHA256 over
`timestamp + "." + raw_body`, signed using that secret). The timestamp must be within five minutes.
Events require verified payment, cannot regress shipment progress, and reject reused IDs with
changed content. Event IDs provide replay protection. Only a verified merchant event can supersede
simulation; a simulation cannot supersede verified tracking.

For a local Razorpay test-order rehearsal, set `JOURNEY_DEMO_FULFILLMENT=true`. My Orders then
shows a shipment simulator. Every resulting event and return eligibility decision is marked as a
simulation. The default is false. No real carrier API or refund provider is configured by this work.

## External buyer reference client

Create a temporary key in My journey → AI buyer demo, then set `NIYAMCART_BUYER_KEY` in the
client process environment and run:

```powershell
.venv\Scripts\python.exe scripts/external_buyer_demo.py --query shirt --budget-paise 200000
```

The independent client discovers catalogue/policy endpoints, deterministically chooses an item,
requests a quote, and prints a review link. It never approves, creates an order, or pays. The
merchant's bounded LLM agent is separate from this reference client's deterministic selection.
Contract routes must stay on the selected merchant origin; redirects are refused to avoid
disclosing the bearer key. The in-app demo exercises the same discovery/quote contract.

## Submission verification improvements

Mission research uses at most three model turns with an eight-second request timeout and no
automatic SDK retries. Provider failures fall back to catalogue results. Interrupted planning
is made retryable after two minutes, and unavailable item descriptions are shown individually.
Saved mission/watch baskets are visible in the shop cart drawer without merging their budgets
or approvals. Basket review can recheck and reopen the same pending test checkout.

Failed provider-order creation is checked against Razorpay's receipt lookup before retrying.
An existing matching provider order is reused; otherwise the same unique receipt is submitted.
Incomplete or ambiguous lookups block retries. Actual payment is still separately approved and
independently verified. No payment success is inferred from a prepared order.

## Payment reference and verification

Provider reconciliation follows Razorpay's documented
[Fetch Payments for an Order](https://razorpay.com/docs/api/orders/fetch-payments/) endpoint and
the existing independently fetched payment finaliser. Money stays in integer paise.

`backend/tests/test_journey.py` covers account isolation, missing details, revision conflicts,
budget/deadline checks, duplicate selection and worker races, expiry/pause, replenishment,
payment reconciliation and same-order retry, signed tracking, return/exchange boundaries,
external quote scope/idempotency, and aftercare tool grounding. Provider interactions in this
suite are fixtures; they are not claimed as live carrier or payment measurements.
