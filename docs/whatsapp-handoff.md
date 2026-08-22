# WhatsApp Handoff

## Current safe scope

NiyamCart has a disabled-by-default, user-controlled WhatsApp handoff foundation. It records an
explicit opt-in, creates a short-lived signed cart-review link, uses a unique idempotency key, and
prepares a utility message the buyer can copy. The link is review-only: it exposes no approval,
order, or payment endpoint. A confirmation message can be prepared only after the backend order is
`paid` and has independently verified provider payment evidence.

No phone number is collected or stored and no external message is transmitted by the current
implementation. If the feature is disabled or preparation fails, the exact in-app cart and verified
payment state continue to work.

## Configuration

```env
WHATSAPP_HANDOFF_ENABLED=false
PUBLIC_APP_URL=https://your-public-app.example
WHATSAPP_LINK_SECRET=at-least-32-random-characters
```

The local feature uses two versioned utility-template names:

- `niyamcart_cart_review_utility_v1`
- `niyamcart_payment_confirmation_utility_v1`

These are internal drafts, not claims of Meta approval.

## External sender still requires approval

Connecting Twilio would transmit a recipient phone number and cart/order context to a third party,
so it was not implemented without explicit destination-specific authorization. When approved, the
sender must use Twilio’s Messages resource with `ContentSid` and `ContentVariables`, not a free-form
business-initiated message. The selected Content SIDs must be WhatsApp-approved; the Sandbox allows
only its pre-approved templates. Do not map a misleading “shipped” Sandbox template to a cart-review
event.

Official references:

- [Twilio WhatsApp Sandbox](https://www.twilio.com/docs/whatsapp/sandbox)
- [Send Content templates](https://www.twilio.com/docs/content/send-templates-created-with-the-content-template-builder)
- [Message template approvals](https://www.twilio.com/docs/whatsapp/tutorial/message-template-approvals-statuses)
- [Twilio Messages resource](https://www.twilio.com/docs/messaging/api/message-resource)

Before enabling an external sender, add destination-specific consent text, minimal PII retention,
Twilio SDK request validation for any status callback, delivery-status idempotency, approved Content
SIDs, and tests proving that provider failure never changes order/payment truth.

