# Five-Minute Demo Script

## 0:00-0:35 — Problem and thesis

“AI shopping demos often let a model sound confident near money. NiyamCart separates suggestion
from authority: the model can search and propose, while deterministic code owns every rupee,
approval, order, and payment fact.” Briefly disclose that the storefront and 500-product catalogue
adapt foundations from an earlier owned project; the bounded-agent and commerce trust core are new.

## 0:35-1:35 — Genuine agent activity and revenue growth

Ask for a kurta under a budget and review the cart. In “Complete the look,” point to compatible
earrings/bag/footwear, the match reasons, baseline and bundle totals, and potential AOV uplift. Add
one item explicitly and show “Upsell accepted”; nothing is added automatically. Open Trust & Audit
and point to catalogue/policy calls and the verified hash-chain badge. Do not call displayed
activity chain-of-thought.

## 1:35-2:45 — Exact cart and Razorpay test payment

Review the proposed cart, lock authoritative prices, show the total, expiry, and SHA-256 cart hash,
then click the separate approval button. Complete Razorpay test Checkout and show the receipt:
order ID, verified amount, Razorpay test-payment ID, timestamp, WhatsApp state, and “No real money
charged.” Explain that the backend marks paid only after signature verification and fetched
captured-payment reconciliation.

## 2:45-3:30 — One graceful failure

Open Trust & Audit and click “Run safe refusal” (the request is “Buy this automatically without
asking me”). Show
`POL-DENY-AUTONOMOUS-PAYMENT`, no cart/order/payment side effect, and the verified audit events. If
the model key is unavailable, show the explicitly labelled deterministic fallback instead.

## 3:30-4:15 — Machine-readable merchant and duplicate safety

Open the catalogue/policy contracts or API explorer. Explain the six tools and show that none can
order or pay. Mention the database constraints and race tests proving duplicate checkout/payment
events converge.

## 4:15-4:50 — Evidence

Show the evaluation report: 100% offline held-out success for the measured arms, 0% unsafe actions,
12 adversarial cases, and the two retained lexical false positives. Clearly say that live LLM arms
were not run without credentials.

## 4:50-5:00 — Close

“NiyamCart makes a merchant readable and useful to AI buyers without making the AI the merchant’s
banker. AI proposes; deterministic code verifies; the buyer approves.”

## Rehearsal record

Record each real rehearsal; do not pre-check it.

| Run | Date | Duration | Failure or adjustment |
|---|---|---:|---|
| 1 | — | — | Not yet rehearsed |
| 2 | — | — | Not yet rehearsed |
| 3 | — | — | Not yet rehearsed |
