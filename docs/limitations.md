# Limitations

- A controlled live Groq tool-calling request has passed, but the frozen live held-out comparison
  has not yet been recorded. Offline fallback metrics remain separately labelled and are not
  presented as live-model quality.
- A complete natural-language-to-verified-payment demo still requires a human to approve the exact
  frozen cart and complete Razorpay Test Checkout.
- Twilio Sandbox delivery is implemented for an explicitly confirmed destination inside its active
  24-hour session, but a real message has not been sent during automated verification. Approved
  utility templates are still required for production-style delivery outside that session.
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
