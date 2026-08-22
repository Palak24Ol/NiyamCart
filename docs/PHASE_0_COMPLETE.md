# Phase 0 Completion Report

Status: **Complete**

Completed on: 2026-08-22

## Scope locked

NiyamCart will be one bounded AI shopping agent for Track 1: AI Growth & Agentic Commerce.

The MVP includes:

- Conversational in-app shopping and checkout handoff.
- An agent-readable catalog with products, variants, stock, compatibility, and policies.
- Explainable, budget-aware upsell and cross-sell recommendations.
- An exact cart proposal that requires explicit human approval.
- Razorpay test-mode order creation and signature verification outside the LLM tool set.
- A readable audit trail for agent decisions, tool calls, approval, and payment state.
- Graceful recovery from at least one realistic failure such as a price or stock change.

Campaign orchestration and autonomous payment are explicitly outside the MVP.

## Source decision

The user confirmed on 2026-08-22 that Kavach Saathi is their project and that they have permission to reuse its code.

The source directory remains read-only:

`C:\Kavach-Saathi\kavach-saathi-main`

Only relevant storefront structure and reusable UI patterns may be selectively adapted. The new project must not copy environment files, credentials, raw-card flows, unrelated security/returns/admin features, or the old product identity.

## Brand decision

- Product: **NiyamCart**
- Tagline: **AI shopping, within your rules.**
- Working repository folder: `C:\BoundedCart`
- No buyer-facing occurrence of `Kavach Saathi` is allowed.

## Technical decisions

- Primary model: `gpt-5.6-luna` through the OpenAI Responses API.
- Agent tools: catalog search, product detail lookup, compatible add-ons, policy lookup, cart proposal, and human escalation.
- Money representation: integer paise, never floating-point currency.
- Payment: human-gated Razorpay test checkout; the LLM cannot create, capture, or verify payments.
- WhatsApp: optional stretch integration for secure cart links and post-payment confirmation only.

## Phase 1 entry criteria

All Phase 1 implementation must preserve these constraints and document every selectively reused source file or extracted component in the adaptation record.

