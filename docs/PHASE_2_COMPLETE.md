# Phase 2 Completion Report

Status: **Complete**

Completed on: 2026-08-22

## Delivered

- Cart and order state machines enforced by service logic and database constraints.
- Authoritative product price, version, and stock checks when proposing and ordering.
- Integer-paise storage for every price, subtotal, total, and payment amount.
- Canonical cart serialization and SHA-256 exact-cart hashing.
- Fifteen-minute frozen-cart approval window.
- Explicit approval requiring the exact frozen cart hash.
- Rejection of expired, altered, unapproved, or previously claimed carts.
- Unique order idempotency keys and one-order-per-cart database constraints.
- Conditional cart claiming and conditional payment finalisation updates.
- Provider event deduplication using unique event IDs.
- Independent payment evidence checks for signature, capture state, provider order, amount, and currency.
- No public payment finalisation endpoint before the Razorpay integration is secured.
- No raw card-number or CVV fields anywhere in the public API schema.

## Graceful failure implemented

If price, product version, or stock changes after a cart is approved, order creation is rejected with `CART_CHANGED`, the cart becomes `invalidated`, and the buyer must review a freshly priced cart.

## Verification

- Backend lint: passed.
- Backend tests: 14 passed.
- Wrong cart hash: rejected.
- Premature approval: rejected.
- Expired approval: rejected.
- Price change after approval: rejected and invalidated.
- Same order request repeated: returns the same order.
- Idempotency key reused for another cart: rejected.
- Two concurrent identical order requests: converge to one order.
- Duplicate payment event: converges to one final result.
- One-paise amount mismatch: cannot mark an order paid.
- Every money-shaped database column uses integer storage.
- Public OpenAPI schema contains no raw-card or CVV field.

## Deferred deliberately

- Compatibility validation waits for the agent-ready relationship layer.
- Razorpay order creation, Checkout, signature verification, payment fetch, and webhooks wait for the dedicated Razorpay phase.
- Frontend frozen-cart and approval screens wait for the frontend integration phase.
