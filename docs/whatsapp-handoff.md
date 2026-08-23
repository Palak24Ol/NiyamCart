# WhatsApp Handoff

## Current safe scope

NiyamCart has a disabled-by-default, user-controlled WhatsApp handoff. It requires explicit opt-in
and exact E.164 destination confirmation, creates a short-lived signed cart-review link, and uses a
unique idempotency key before any provider call. The link is review-only: it exposes no approval,
order, or payment endpoint. A confirmation message can be sent only after the backend order is
`paid` and has independently verified Razorpay payment evidence.

The raw destination is held only for the request to Twilio and is not stored in the handoff or
audit payload. Persisted records use a keyed destination fingerprint. Provider failure never changes
cart, order, or payment truth, and the in-app flow remains available.

## Configuration

```env
WHATSAPP_HANDOFF_ENABLED=false
PUBLIC_APP_URL=https://your-public-app.example
WHATSAPP_LINK_SECRET=at-least-32-random-characters
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=whatsapp:+17372508034
TWILIO_REVIEW_CONTENT_SID=
TWILIO_CONFIRMATION_CONTENT_SID=
```

The local feature uses two versioned utility-template names:

- `niyamcart_cart_review_utility_v1`
- `niyamcart_payment_confirmation_utility_v1`

These are internal drafts, not claims of Meta approval.

## Sandbox and approved templates

The trial Sandbox can send NiyamCart's free-form review and confirmation bodies only while the
recipient has an active 24-hour session after sending the Sandbox join message. No Content SID is
required for that demo path. For messages outside that session or a production sender, create and
approve the matching WhatsApp utility templates, then set the two `HX...` Content SIDs. The sender
automatically prefers `ContentSid` plus `ContentVariables` when those values are configured.

Official references:

- [Twilio WhatsApp Sandbox](https://www.twilio.com/docs/whatsapp/sandbox)
- [Send Content templates](https://www.twilio.com/docs/content/send-templates-created-with-the-content-template-builder)
- [Message template approvals](https://www.twilio.com/docs/whatsapp/tutorial/message-template-approvals-statuses)
- [Twilio Messages resource](https://www.twilio.com/docs/messaging/api/message-resource)

The implementation includes destination-specific consent, minimal PII retention, send
idempotency, and tests proving that provider failure never changes order/payment truth. A future
public status-callback endpoint must validate Twilio signatures before it is enabled.
