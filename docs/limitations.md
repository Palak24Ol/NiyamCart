# Limitations

- Live OpenAI single-shot and full-agent held-out runs were not executed because no API key was
  configured. Offline fallback metrics are reported separately and are not presented as model
  quality.
- A complete natural-language-to-verified-payment demo still needs valid OpenAI and Razorpay test
  credentials plus a human completing Razorpay Checkout.
- The WhatsApp feature prepares a user-controlled handoff only. It does not collect phone numbers
  or transmit to Twilio until destination-specific authorization and approved template IDs exist.
- The catalogue is a fixed demonstration dataset. Inventory does not integrate with a real merchant
  ERP, and the synthetic compatibility rules should not be treated as universal product expertise.
- SQLite is intended for local demonstration. A production deployment should use PostgreSQL and
  validate its row-locking/concurrency behavior under load.
- Authentication, customer accounts, addresses, fulfilment, refunds, taxes, and real-money mode are
  intentionally out of scope.
- Payment is Razorpay test mode only. Live keys are rejected.
- The public audit is tamper-evident, not an externally anchored ledger. A database administrator
  able to rewrite both events and hashes is outside its threat model.
- The keyword fallback can return lexically related but semantically unsuitable products; the
  retained evaluation failures demonstrate this limitation.
- External HTTPS deployment, operational monitoring, retention controls, and production incident
  response are not included in the MVP.

