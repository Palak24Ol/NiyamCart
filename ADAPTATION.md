# Adaptation and Provenance

NiyamCart is a new Razorpay AI Buildathon Track 1 product. It selectively adapts relevant buyer-storefront foundations from Kavach Saathi with confirmed permission.

## Source inspected

- Local source: `C:\Kavach-Saathi\kavach-saathi-main`
- Commit: `895208eb9b1f465ec23e1d6770b0bd6b7b669c5f`
- Git authors observed: Palak Jaiswal, Manya Gupta, and `manya1632`
- Remotes observed: `Palak24Ol/Kavach-Saathi` and `manya1632/Kavach-Saathi`
- Root license: not found

## Permission status

Confirmed by the user on 2026-08-22. The user stated that Kavach Saathi is their project and that they have permission to reuse its code.

## Frontend checkpoint implemented

The buyer-facing product discovery, cart, and checkout-review concepts were reimplemented as a clean modular Next.js application. No source file was copied wholesale. The original monolithic storefront was used to identify relevant commerce behavior, while all unrelated workflows and the previous visual identity were excluded.

Active frontend files are:

- `app/layout.tsx`
- `app/page.tsx`
- `app/globals.css`
- `components/NiyamCartApp.tsx`
- `lib/catalog.ts`
- `lib/agent.ts`
- `lib/checkout.ts`
- `lib/whatsapp.ts`

No credentials, environment values, user records, raw-card forms, media files, or old branding were imported.

## Catalogue checkpoint implemented

- Reused the authorized `data/seed/products.json` product records only.
- Reused the 500 primary product images only; buyer, seller, order, address, review, return, label, and multi-angle data were excluded.
- Normalized every monetary value from integer rupees to integer paise.
- Replaced inherited presentation phrases with neutral NiyamCart catalogue language.
- Converted 500 PNG primary images to optimized WebP files, reducing the set from approximately 61 MB to approximately 8 MB.
- Added a reproducible importer at `scripts/import_catalog.py` instead of relying on the original repository at runtime.
- Preserved a fixed catalogue of 500 unique products across 10 categories for repeatable agent evaluation.

## Implemented selective reuse

| Foundation | Actual handling | Buildathon-specific work |
|---|---|---|
| Buyer UI shell and visual concepts | Reimplemented and substantially refactored | Live agent workspace, policy refusal, audit, exact approval, accessibility |
| Product/cart/checkout concepts | Reimplemented | Frozen hash, separate approval, Razorpay test Checkout, verified state |
| FastAPI/data foundation | Recreated as a focused service | New catalogue, policy, agent, commerce, audit, evaluation, and handoff routes |
| Razorpay patterns | Rewritten and hardened | Integer paise, fetched truth, raw webhook verification, races, finaliser |
| Idempotency concepts | Implemented with database constraints | Order, checkout, payment-event, webhook, and handoff convergence |
| LLM provider concept | Replaced with bounded OpenAI Responses provider | Six strict tools, cost/step/revision budgets, repair and degraded mode |
| Test concepts | Rebuilt for this trust boundary | 69 unit/integration/property/race/reliability tests and browser verification |

## Not reused

Existing agents, orchestration graphs, safety/return/delivery/address/review workflows, image and voice providers, large media assets, raw-card demo payment flow, existing secrets, and the old migration history.

## New Buildathon core

- Bounded tool-calling loop
- Six typed tools with no financial side effects
- Agent-readable catalogue and policy contracts
- Deterministic policy engine
- Cart-hash approval binding
- Hardened Razorpay reconciliation and finalisation
- Audit design and verification
- Prompt-injection and failure tests
- Controlled evaluation with baselines
- Redacted SHA-256 audit chains and verification endpoint
- Versioned development, held-out, and adversarial evaluation datasets
- Signed, review-only local WhatsApp handoff foundation

No code or asset will be presented as newly authored if it was inherited from prior work.
