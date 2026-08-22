# Architecture and Scope Decisions

## D-001 - Separate clean repository

Decision: Build in `C:\BoundedCart`; treat Kavach Saathi as read-only reference.

Reason: The source working tree is dirty, contains unrelated features and local configuration, and must remain recoverable.

## D-002 - Selective extraction, not whole-repository copy

Decision: Extract small buyer-facing UI patterns and selected infrastructure ideas. Do not copy the 3,000-line storefront or existing agent/orchestration system wholesale.

Reason: This reduces security risk, legacy coupling, dependency weight, and rebranding ambiguity.

## D-003 - One bounded agent

Decision: One tool-selecting agent with six tools and an eight-step limit.

Reason: Clearer agentic behavior, easier evaluation, smaller attack surface, and stronger five-minute explanation.

## D-004 - No financial side-effect tools

Decision: The LLM can only search, inspect, read policy, propose a cart, or escalate.

Reason: Buyer approval and deterministic backend state transitions must be structurally unavoidable.

## D-005 - Primary LLM

Decision: Start evaluation with `gpt-5.6-luna` at low reasoning effort; compare `gpt-5.6-terra` only if Luna misses declared thresholds.

Reason: Luna supports function calling and structured output at a low token price. Model selection remains evidence-driven.

## D-006 - WhatsApp is stretch-only

Decision: Add secure cart handoff and verified utility notification only after the core checkout and evaluation pass.

Reason: The core demo must not depend on Twilio/WhatsApp availability, templates, or sandbox state.

