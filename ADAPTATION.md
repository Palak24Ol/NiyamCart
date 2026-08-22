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

No credentials, environment values, user records, raw-card forms, media files, or old branding were imported.

## Planned selective reuse

| Foundation | Planned handling | Buildathon-specific work |
|---|---|---|
| Buyer UI shell and visual patterns | Extract and substantially refactor | New focused agent workspace and component structure |
| Product/cart/checkout visual components | Extract and rewrite | Frozen-cart approval, policy refusal, payment verification, audit timeline |
| FastAPI/PostgreSQL foundation | Recreate from relevant patterns | New minimal domain model and routes |
| Razorpay wrapper and webhook patterns | Rewrite and harden | Integer paise, reconciliation, idempotency, locked finalisation |
| Redis idempotency pattern | Reimplement narrowly | Session/operation limits and duplicate prevention |
| Reasoning-provider abstraction | Replace with bounded OpenAI Responses provider | Six-tool loop, usage/cost capture, typed failures |
| Test/Docker patterns | Adapt | New core, adversarial, payment, and evaluation coverage |

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

No code or asset will be presented as newly authored if it was inherited from prior work.
