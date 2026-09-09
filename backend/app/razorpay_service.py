from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .audit import append_audit
from .commerce import PaymentEvidence, finalise_payment
from .commerce_models import (
    CartOfferSelection,
    Order,
    PaymentEvent,
    RazorpayCheckout,
    RazorpayWebhookReceipt,
)
from .razorpay_schemas import (
    PaymentVerificationResponse,
    RazorpayCheckoutResponse,
    RazorpayWebhookResponse,
    VerifyRazorpayPaymentRequest,
)


class RazorpayError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class RazorpaySettings:
    key_id: str
    key_secret: str
    webhook_secret: str
    api_base_url: str = "https://api.razorpay.com/v1"

    @classmethod
    def from_env(cls) -> RazorpaySettings | None:
        key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
        key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
        webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
        if not key_id and not key_secret and not webhook_secret:
            return None
        if not key_id or not key_secret:
            raise RazorpayError(
                503,
                "RAZORPAY_NOT_CONFIGURED",
                "Both Razorpay test key ID and secret are required",
            )
        if not key_id.startswith("rzp_test_"):
            raise RazorpayError(
                503,
                "RAZORPAY_TEST_MODE_REQUIRED",
                "NiyamCart accepts only Razorpay test-mode credentials",
            )
        return cls(key_id=key_id, key_secret=key_secret, webhook_secret=webhook_secret)


class RazorpayGateway(Protocol):
    key_id: str

    def create_order(self, payload: dict[str, object]) -> dict[str, object]: ...

    def fetch_payment(self, payment_id: str) -> dict[str, object]: ...

    def verify_checkout_signature(
        self, provider_order_id: str, payment_id: str, signature: str
    ) -> bool: ...

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool: ...


class RazorpayHttpGateway:
    def __init__(self, settings: RazorpaySettings) -> None:
        self.settings = settings
        self.key_id = settings.key_id

    def _request(
        self, method: str, path: str, *, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            response = httpx.request(
                method,
                f"{self.settings.api_base_url}{path}",
                auth=(self.settings.key_id, self.settings.key_secret),
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            message = (
                "Razorpay rejected the test credentials. Check the running backend's test key pair."
                if status in {401, 403}
                else "Razorpay rejected the checkout request. "
                "Check the selected offer and test configuration."
                if status == 400
                else "Razorpay is temporarily unavailable. Retry this same basket after a moment."
            )
            raise RazorpayError(503, f"RAZORPAY_HTTP_{status}", message) from error
        except (httpx.HTTPError, ValueError) as error:
            raise RazorpayError(
                503,
                "RAZORPAY_UNAVAILABLE",
                "Razorpay did not return a usable response; no payment state was assumed",
            ) from error
        if not isinstance(body, dict):
            raise RazorpayError(502, "INVALID_RAZORPAY_RESPONSE", "Invalid Razorpay response")
        return body

    def create_order(self, payload: dict[str, object]) -> dict[str, object]:
        return self._request("POST", "/orders", payload=payload)

    def fetch_orders_by_receipt(self, receipt: str) -> dict[str, object]:
        return self._request("GET", "/orders?" + urlencode({"receipt": receipt, "count": 100}))

    def fetch_payment(self, payment_id: str) -> dict[str, object]:
        if not payment_id.startswith("pay_") or not payment_id.replace("_", "").isalnum():
            raise RazorpayError(422, "INVALID_PAYMENT_ID", "Invalid Razorpay payment ID")
        return self._request("GET", f"/payments/{payment_id}")

    def fetch_order_payments(self, provider_order_id: str) -> dict[str, object]:
        if (
            not provider_order_id.startswith("order_")
            or not provider_order_id.replace("_", "").isalnum()
        ):
            raise RazorpayError(422, "INVALID_ORDER_ID", "Invalid Razorpay order ID")
        return self._request("GET", f"/orders/{provider_order_id}/payments")

    def verify_checkout_signature(
        self, provider_order_id: str, payment_id: str, signature: str
    ) -> bool:
        message = f"{provider_order_id}|{payment_id}".encode()
        expected = hmac.new(self.settings.key_secret.encode(), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        if not self.settings.webhook_secret:
            raise RazorpayError(
                503,
                "WEBHOOK_NOT_CONFIGURED",
                "Razorpay webhook verification is not configured",
            )
        expected = hmac.new(
            self.settings.webhook_secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


def configured_gateway() -> RazorpayGateway | None:
    settings = RazorpaySettings.from_env()
    return RazorpayHttpGateway(settings) if settings else None


def require_gateway(gateway: RazorpayGateway | None) -> RazorpayGateway:
    if gateway is None:
        raise RazorpayError(
            503,
            "RAZORPAY_NOT_CONFIGURED",
            "Razorpay test mode is unavailable until test credentials are configured",
        )
    if not gateway.key_id.startswith("rzp_test_"):
        raise RazorpayError(
            503,
            "RAZORPAY_TEST_MODE_REQUIRED",
            "NiyamCart accepts only Razorpay test-mode credentials",
        )
    return gateway


def _checkout_response(
    checkout: RazorpayCheckout, gateway: RazorpayGateway
) -> RazorpayCheckoutResponse:
    if checkout.state != "ready" or not checkout.provider_order_id:
        raise RazorpayError(409, "CHECKOUT_NOT_READY", "Razorpay checkout is not ready")
    return RazorpayCheckoutResponse(
        internal_order_id=checkout.order_id,
        razorpay_order_id=checkout.provider_order_id,
        key_id=gateway.key_id,
        amount_paise=checkout.amount_paise,
        currency=checkout.currency,
    )


def create_razorpay_checkout(
    db: Session, order_id: str, gateway: RazorpayGateway | None
) -> RazorpayCheckoutResponse:
    gateway = require_gateway(gateway)
    order = db.get(Order, order_id)
    if order is None:
        raise RazorpayError(404, "ORDER_NOT_FOUND", "Order not found")
    if order.status != "payment_pending":
        raise RazorpayError(409, "INVALID_ORDER_STATE", "Only pending orders can open checkout")

    existing = db.get(RazorpayCheckout, order.id)
    recovered_provider_order = None
    if existing is not None:
        if existing.state == "ready":
            return _checkout_response(existing, gateway)
        if existing.state == "creating":
            raise RazorpayError(409, "CHECKOUT_IN_PROGRESS", "Checkout creation is in progress")
        fetch = getattr(gateway, "fetch_orders_by_receipt", None)
        if fetch is None:
            raise RazorpayError(
                503,
                "CHECKOUT_CREATION_FAILED",
                "The earlier provider-order result is uncertain; manual review is required",
            )
        collection = fetch(existing.receipt)
        items = collection.get("items") if isinstance(collection, dict) else None
        if (
            not isinstance(items, list)
            or collection.get("count") != len(items)
            or len(items) >= 100
            or any(not isinstance(p, dict) for p in items)
        ):
            raise RazorpayError(
                502,
                "CHECKOUT_LOOKUP_INCOMPLETE",
                "Provider order lookup was incomplete; retry blocked",
            )
        matches = [p for p in items if p.get("receipt") == existing.receipt]
        if len(matches) > 1:
            raise RazorpayError(
                409, "CHECKOUT_LOOKUP_AMBIGUOUS", "Multiple provider orders need merchant review"
            )
        recovered_provider_order = matches[0] if matches else None
        claim = db.execute(
            update(RazorpayCheckout)
            .where(
                RazorpayCheckout.order_id == order.id,
                RazorpayCheckout.state == "failed",
            )
            .values(state="creating", failure_code=None)
        )
        db.commit()
        if claim.rowcount != 1:
            raise RazorpayError(
                409, "CHECKOUT_IN_PROGRESS", "Another checkout retry is in progress"
            )
        db.refresh(existing)

    checkout = existing or RazorpayCheckout(
        order_id=order.id,
        state="creating",
        receipt=f"nc-{order.id}",
        amount_paise=order.total_paise,
        currency=order.currency,
        cart_hash=order.cart_hash,
    )
    db.add(checkout)
    append_audit(
        db,
        "order",
        order.id,
        "checkout_creation_started",
        {
            "amount_paise": checkout.amount_paise,
            "currency": checkout.currency,
            "receipt": checkout.receipt,
            "cart_hash": checkout.cart_hash,
        },
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(RazorpayCheckout, order.id)
        if existing and existing.state == "ready":
            return _checkout_response(existing, gateway)
        raise RazorpayError(
            409, "CHECKOUT_IN_PROGRESS", "Checkout creation is in progress"
        ) from None

    request_payload: dict[str, object] = {
        "amount": checkout.amount_paise,
        "currency": checkout.currency,
        "receipt": checkout.receipt,
        "notes": {
            "internal_order_id": order.id,
            "cart_hash": order.cart_hash,
            "mode": "test",
        },
    }
    selected_offer = db.get(CartOfferSelection, order.cart_id)
    if selected_offer and selected_offer.provider_offer_id:
        request_payload["offers"] = [selected_offer.provider_offer_id]
        request_payload["force_offer"] = True
        request_payload["notes"]["selected_offer_key"] = selected_offer.offer_key
    try:
        provider_order = recovered_provider_order or gateway.create_order(request_payload)
        provider_order_id = provider_order.get("id")
        valid = (
            isinstance(provider_order_id, str)
            and provider_order_id.startswith("order_")
            and provider_order.get("amount") == checkout.amount_paise
            and provider_order.get("currency") == checkout.currency
            and provider_order.get("receipt") == checkout.receipt
            and provider_order.get("status")
            in ({"created", "attempted"} if recovered_provider_order else {"created"})
        )
        if not valid:
            raise RazorpayError(
                502,
                "RAZORPAY_ORDER_MISMATCH",
                "Razorpay returned an order that does not match the approved cart",
            )
    except RazorpayError as error:
        checkout.state = "failed"
        checkout.failure_code = error.code
        append_audit(
            db,
            "order",
            order.id,
            "checkout_creation_failed",
            {"error": error.code},
        )
        db.commit()
        raise

    checkout.provider_order_id = provider_order_id
    checkout.state = "ready"
    order.provider_order_id = provider_order_id
    append_audit(
        db,
        "order",
        order.id,
        "checkout_ready",
        {
            "provider_order_id": provider_order_id,
            "receipt": checkout.receipt,
            "amount_paise": checkout.amount_paise,
            "currency": checkout.currency,
            "cart_hash": checkout.cart_hash,
        },
    )
    db.commit()
    return _checkout_response(checkout, gateway)


def _signature_failure_event_id(payment_id: str, signature: str) -> str:
    fingerprint = hashlib.sha256(f"{payment_id}|{signature}".encode()).hexdigest()
    return f"callback-invalid:{fingerprint}"


def _callback_event_id(payment_id: str) -> str:
    return f"callback:{hashlib.sha256(payment_id.encode()).hexdigest()}"


def _reconcile_fetched_payment(
    db: Session,
    order: Order,
    gateway: RazorpayGateway,
    payment_id: str,
    event_id: str,
    event_type: str,
) -> tuple[Order, PaymentEvent]:
    payment = gateway.fetch_payment(payment_id)
    fetched_id = payment.get("id")
    amount = payment.get("amount")
    currency = payment.get("currency")
    provider_order_id = payment.get("order_id")
    captured = payment.get("captured") is True and payment.get("status") == "captured"
    provider_offer_id = payment.get("offer_id")
    if (
        fetched_id != payment_id
        or not isinstance(amount, int)
        or not isinstance(currency, str)
        or not isinstance(provider_order_id, str)
    ):
        raise RazorpayError(
            502,
            "INVALID_PAYMENT_RESPONSE",
            "Razorpay payment data was incomplete; no payment state was assumed",
        )
    evidence = PaymentEvidence(
        provider_event_id=event_id,
        event_type=event_type,
        provider_order_id=provider_order_id,
        provider_payment_id=payment_id,
        amount_paise=amount,
        currency=currency,
        signature_verified=True,
        captured=captured,
        provider_offer_id=provider_offer_id if isinstance(provider_offer_id, str) else None,
    )
    return finalise_payment(db, order.id, evidence)


def verify_checkout_payment(
    db: Session,
    request: VerifyRazorpayPaymentRequest,
    gateway: RazorpayGateway | None,
) -> PaymentVerificationResponse:
    gateway = require_gateway(gateway)
    order = db.get(Order, request.internal_order_id)
    checkout = db.get(RazorpayCheckout, request.internal_order_id)
    if order is None or checkout is None or checkout.state != "ready":
        raise RazorpayError(404, "CHECKOUT_NOT_FOUND", "Checkout not found")
    if (
        not checkout.provider_order_id
        or request.razorpay_order_id != checkout.provider_order_id
        or order.provider_order_id != checkout.provider_order_id
    ):
        raise RazorpayError(
            409,
            "PROVIDER_ORDER_MISMATCH",
            "The callback order does not match the server-stored checkout order",
        )

    signature_ok = gateway.verify_checkout_signature(
        checkout.provider_order_id,
        request.razorpay_payment_id,
        request.razorpay_signature,
    )
    if not signature_ok:
        _, event = finalise_payment(
            db,
            order.id,
            PaymentEvidence(
                provider_event_id=_signature_failure_event_id(
                    request.razorpay_payment_id, request.razorpay_signature
                ),
                event_type="checkout.callback",
                provider_order_id=checkout.provider_order_id,
                provider_payment_id=request.razorpay_payment_id,
                amount_paise=order.total_paise,
                currency=order.currency,
                signature_verified=False,
                captured=False,
            ),
        )
        raise RazorpayError(400, "INVALID_PAYMENT_SIGNATURE", event.reason)

    event_id = _callback_event_id(request.razorpay_payment_id)
    existing_event = db.get(PaymentEvent, event_id)
    if existing_event is not None:
        if not existing_event.accepted:
            raise RazorpayError(
                409,
                "PAYMENT_NOT_VERIFIED",
                f"Payment was not finalised: {existing_event.reason}",
            )
        return PaymentVerificationResponse(
            internal_order_id=order.id,
            status=order.status,
            payment_status="verified",
            razorpay_payment_id=request.razorpay_payment_id,
            duplicate=True,
            amount_paise=order.total_paise,
            currency=order.currency,
            verified_at=order.paid_at,
        )
    reconciled_order, event = _reconcile_fetched_payment(
        db,
        order,
        gateway,
        request.razorpay_payment_id,
        event_id,
        "checkout.callback",
    )
    if not event.accepted:
        raise RazorpayError(
            409,
            "PAYMENT_NOT_VERIFIED",
            f"Payment was not finalised: {event.reason}",
        )
    return PaymentVerificationResponse(
        internal_order_id=order.id,
        status=reconciled_order.status,
        payment_status="verified",
        razorpay_payment_id=request.razorpay_payment_id,
        duplicate=False,
        amount_paise=reconciled_order.total_paise,
        currency=reconciled_order.currency,
        verified_at=reconciled_order.paid_at,
    )


def _claim_webhook(
    db: Session, event_id: str, event_type: str, raw_body: bytes
) -> tuple[RazorpayWebhookReceipt, bool]:
    existing = db.get(RazorpayWebhookReceipt, event_id)
    if existing is not None:
        if existing.status == "retryable":
            existing.status = "processing"
            existing.reason = None
            db.commit()
            return existing, False
        return existing, True
    receipt = RazorpayWebhookReceipt(
        event_id=event_id,
        event_type=event_type,
        payload_hash=hashlib.sha256(raw_body).hexdigest(),
        status="processing",
    )
    db.add(receipt)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.get(RazorpayWebhookReceipt, event_id), True
    return receipt, False


def process_razorpay_webhook(
    db: Session,
    raw_body: bytes,
    signature: str,
    event_id: str,
    gateway: RazorpayGateway | None,
) -> RazorpayWebhookResponse:
    gateway = require_gateway(gateway)
    if not signature or not gateway.verify_webhook_signature(raw_body, signature):
        raise RazorpayError(400, "INVALID_WEBHOOK_SIGNATURE", "Invalid webhook signature")
    if not event_id or len(event_id) > 112:
        raise RazorpayError(422, "INVALID_WEBHOOK_EVENT_ID", "Missing webhook event ID")
    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RazorpayError(400, "INVALID_WEBHOOK_PAYLOAD", "Invalid webhook payload") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("event"), str):
        raise RazorpayError(400, "INVALID_WEBHOOK_PAYLOAD", "Invalid webhook payload")

    event_type = payload["event"]
    receipt, duplicate = _claim_webhook(db, event_id, event_type, raw_body)
    if duplicate:
        return RazorpayWebhookResponse(
            duplicate=True,
            processed=receipt.status in {"processed", "ignored"},
            reason=receipt.reason or receipt.status,
        )

    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    if not isinstance(payment, dict):
        payment = {}
    provider_order_id = payment.get("order_id")
    payment_id = payment.get("id")
    receipt.provider_order_id = provider_order_id if isinstance(provider_order_id, str) else None
    receipt.provider_payment_id = payment_id if isinstance(payment_id, str) else None

    if event_type not in {"payment.captured", "order.paid", "payment.failed"}:
        receipt.status = "ignored"
        receipt.reason = "unsupported_event"
        db.commit()
        return RazorpayWebhookResponse(duplicate=False, processed=False, reason="unsupported_event")
    if not isinstance(provider_order_id, str) or not isinstance(payment_id, str):
        receipt.status = "ignored"
        receipt.reason = "missing_payment_entity"
        db.commit()
        return RazorpayWebhookResponse(
            duplicate=False, processed=False, reason="missing_payment_entity"
        )

    checkout = db.query(RazorpayCheckout).filter_by(provider_order_id=provider_order_id).first()
    order = db.get(Order, checkout.order_id) if checkout else None
    if checkout is None or order is None:
        receipt.status = "ignored"
        receipt.reason = "unknown_provider_order"
        db.commit()
        return RazorpayWebhookResponse(
            duplicate=False, processed=False, reason="unknown_provider_order"
        )

    try:
        if event_type in {"payment.captured", "order.paid"}:
            _, payment_event = _reconcile_fetched_payment(
                db,
                order,
                gateway,
                payment_id,
                f"webhook:{event_id}",
                event_type,
            )
        else:
            failed_amount = payment.get("amount")
            failed_currency = payment.get("currency")
            if not isinstance(failed_amount, int) or not isinstance(failed_currency, str):
                receipt.status = "ignored"
                receipt.reason = "invalid_failed_payment_entity"
                db.commit()
                return RazorpayWebhookResponse(
                    duplicate=False,
                    processed=False,
                    reason="invalid_failed_payment_entity",
                )
            _, payment_event = finalise_payment(
                db,
                order.id,
                PaymentEvidence(
                    provider_event_id=f"webhook:{event_id}",
                    event_type=event_type,
                    provider_order_id=provider_order_id,
                    provider_payment_id=payment_id,
                    amount_paise=failed_amount,
                    currency=failed_currency,
                    signature_verified=True,
                    captured=False,
                ),
            )
    except RazorpayError as error:
        receipt.status = "retryable"
        receipt.reason = error.code
        db.commit()
        raise

    receipt.status = "processed"
    receipt.reason = payment_event.reason
    db.commit()
    return RazorpayWebhookResponse(
        duplicate=False,
        processed=True,
        reason=payment_event.reason,
    )
