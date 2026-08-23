from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .audit import append_audit
from .commerce import CommerceError, load_cart
from .commerce_models import Cart, Order
from .whatsapp_delivery import WhatsAppDeliveryError, WhatsAppSender
from .whatsapp_models import WhatsAppHandoff, WhatsAppOptIn
from .whatsapp_schemas import (
    WhatsAppConfirmationRequest,
    WhatsAppHandoffResponse,
    WhatsAppReviewRequest,
)

CONSENT_VERSION = "whatsapp-delivery-v2"
REVIEW_TEMPLATE = "niyamcart_cart_review_utility_v1"
CONFIRMATION_TEMPLATE = "niyamcart_payment_confirmation_utility_v1"


@dataclass(frozen=True)
class WhatsAppSettings:
    enabled: bool
    public_app_url: str = "http://localhost:3000"
    link_secret: str = ""

    @classmethod
    def from_env(cls) -> WhatsAppSettings:
        enabled = os.getenv("WHATSAPP_HANDOFF_ENABLED", "false").lower() == "true"
        settings = cls(
            enabled=enabled,
            public_app_url=os.getenv("PUBLIC_APP_URL", "http://localhost:3000").rstrip("/"),
            link_secret=os.getenv("WHATSAPP_LINK_SECRET", "").strip(),
        )
        if enabled and len(settings.link_secret) < 32:
            raise RuntimeError("WHATSAPP_LINK_SECRET must contain at least 32 characters")
        return settings


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_review_token(cart: Cart, settings: WhatsAppSettings) -> str:
    if not cart.cart_hash or not cart.expires_at:
        raise CommerceError(409, "CART_NOT_FROZEN", "Freeze the cart before sharing it")
    expires_at = (
        cart.expires_at.replace(tzinfo=UTC)
        if cart.expires_at.tzinfo is None
        else cart.expires_at
    )
    payload = {
        "cart_id": cart.id,
        "cart_hash": cart.cart_hash,
        "expires_at": int(expires_at.timestamp()),
        "purpose": "cart_review_only",
    }
    encoded = _encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    signature = hmac.new(settings.link_secret.encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{_encode(signature)}"


def load_review_cart(db: Session, token: str, settings: WhatsAppSettings) -> Cart:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected = hmac.new(
            settings.link_secret.encode(), encoded.encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _decode(supplied_signature)):
            raise ValueError("invalid signature")
        payload = json.loads(_decode(encoded))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CommerceError(400, "INVALID_REVIEW_LINK", "The review link is invalid") from error
    if payload.get("purpose") != "cart_review_only":
        raise CommerceError(400, "INVALID_REVIEW_LINK", "The review link is invalid")
    if int(payload.get("expires_at", 0)) <= int(datetime.now(UTC).timestamp()):
        raise CommerceError(410, "REVIEW_LINK_EXPIRED", "The cart review link expired")
    cart = load_cart(db, str(payload.get("cart_id", "")))
    if cart.cart_hash != payload.get("cart_hash"):
        raise CommerceError(409, "CART_MUTATED", "The shared cart no longer matches")
    return cart


def _fingerprint(destination: str, settings: WhatsAppSettings) -> str:
    return hmac.new(
        settings.link_secret.encode(), destination.encode(), hashlib.sha256
    ).hexdigest()


def _existing(db: Session, key: str) -> WhatsAppHandoff | None:
    return db.scalar(select(WhatsAppHandoff).where(WhatsAppHandoff.idempotency_key == key))


def _response(handoff: WhatsAppHandoff, *, duplicate: bool) -> WhatsAppHandoffResponse:
    messages = {
        "ready_for_user_share": (
            "External delivery is unavailable; copy this safe utility message into WhatsApp."
        ),
        "sending": "WhatsApp delivery is already being processed.",
        "sent": "Sent to the explicitly confirmed WhatsApp destination.",
        "delivery_failed": (
            "WhatsApp delivery was not accepted; use the safe copyable message instead."
        ),
    }
    return WhatsAppHandoffResponse(
        status=handoff.status,  # type: ignore[arg-type]
        duplicate=duplicate,
        template_name=handoff.template_name,
        review_url=(
            str(handoff.payload.get("review_url"))
            if handoff.payload.get("review_url")
            else None
        ),
        share_text=str(handoff.payload["share_text"]),
        message=messages.get(handoff.status, "WhatsApp handoff prepared."),
        provider_message_id=(
            str(handoff.payload["provider_message_id"])
            if handoff.payload.get("provider_message_id")
            else None
        ),
        destination_fingerprint=(
            str(handoff.payload["destination_fingerprint"])[:12]
            if handoff.payload.get("destination_fingerprint")
            else None
        ),
    )


def _disabled(message: str) -> WhatsAppHandoffResponse:
    return WhatsAppHandoffResponse(
        status="disabled",
        duplicate=False,
        template_name=None,
        review_url=None,
        share_text=None,
        message=message,
    )


def _create_and_deliver(
    db: Session,
    *,
    handoff: WhatsAppHandoff,
    sender: WhatsAppSender | None,
    destination: str,
    variables: dict[str, str],
    audit_scope: str,
    audit_scope_id: str,
) -> WhatsAppHandoffResponse:
    existing = _existing(db, handoff.idempotency_key)
    if existing is not None:
        return _response(existing, duplicate=True)
    db.add(handoff)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _existing(db, handoff.idempotency_key)
        if existing is None:
            raise
        return _response(existing, duplicate=True)

    if sender is None:
        handoff.status = "ready_for_user_share"
    else:
        try:
            delivery = sender.send(
                kind=handoff.kind,
                destination=destination,
                body=str(handoff.payload["share_text"]),
                variables=variables,
            )
            handoff.status = "sent"
            handoff.payload = {
                **handoff.payload,
                "provider_message_id": delivery.provider_message_id,
                "provider_status": delivery.provider_status,
            }
        except WhatsAppDeliveryError as error:
            handoff.status = "delivery_failed"
            handoff.payload = {**handoff.payload, "delivery_error": error.code}
    append_audit(
        db,
        audit_scope,
        audit_scope_id,
        f"whatsapp_{handoff.kind}_{handoff.status}",
        {
            "template_name": handoff.template_name,
            "destination_fingerprint": str(
                handoff.payload["destination_fingerprint"]
            )[:12],
            "status": handoff.status,
            "permits_financial_approval": False,
        },
    )
    db.commit()
    return _response(handoff, duplicate=False)


def prepare_cart_review_handoff(
    db: Session,
    cart_id: str,
    request: WhatsAppReviewRequest,
    settings: WhatsAppSettings,
    sender: WhatsAppSender | None = None,
) -> WhatsAppHandoffResponse:
    if not settings.enabled:
        return _disabled(
            "WhatsApp handoff is disabled; continue with the in-app exact-cart review."
        )
    cart = load_cart(db, cart_id)
    if cart.status != "frozen" or cart.cart_hash != request.cart_hash:
        raise CommerceError(
            409,
            "CART_NOT_REVIEWABLE",
            "Only the exact frozen cart can be shared for review",
        )
    if db.get(WhatsAppOptIn, cart.id) is None:
        db.add(WhatsAppOptIn(cart_id=cart.id, consent_version=CONSENT_VERSION))
    token = create_review_token(cart, settings)
    review_url = f"{settings.public_app_url}/review/{token}"
    destination_fingerprint = _fingerprint(request.destination, settings)
    key = f"review:{cart.id}:{cart.cart_hash}:{destination_fingerprint}"
    share_text = (
        f"NiyamCart cart {cart.id[:8]} totals INR {cart.total_paise / 100:,.2f}. "
        f"Review it here: {review_url}. Approval and payment happen only in NiyamCart."
    )
    handoff = WhatsAppHandoff(
        cart_id=cart.id,
        kind="cart_review",
        template_name=REVIEW_TEMPLATE,
        idempotency_key=key,
        status="sending",
        payload={
            "review_url": review_url,
            "share_text": share_text,
            "destination_fingerprint": destination_fingerprint,
            "permits_financial_approval": False,
        },
    )
    return _create_and_deliver(
        db,
        handoff=handoff,
        sender=sender,
        destination=request.destination,
        variables={
            "1": cart.id[:8],
            "2": f"{cart.total_paise / 100:.2f}",
            "3": review_url,
        },
        audit_scope="cart",
        audit_scope_id=cart.id,
    )


def prepare_payment_confirmation_handoff(
    db: Session,
    order_id: str,
    request: WhatsAppConfirmationRequest,
    settings: WhatsAppSettings,
    sender: WhatsAppSender | None = None,
) -> WhatsAppHandoffResponse:
    if not settings.enabled:
        return _disabled(
            "WhatsApp handoff is disabled; the in-app verified state remains available."
        )
    order = db.get(Order, order_id)
    if order is None:
        raise CommerceError(404, "ORDER_NOT_FOUND", "Order not found")
    if order.status != "paid" or not order.provider_payment_id:
        raise CommerceError(
            409,
            "PAYMENT_NOT_VERIFIED",
            "A confirmation can be sent only after backend payment verification",
        )
    if db.get(WhatsAppOptIn, order.cart_id) is None:
        raise CommerceError(409, "WHATSAPP_NOT_OPTED_IN", "The buyer did not opt in")
    destination_fingerprint = _fingerprint(request.destination, settings)
    reviews = db.scalars(
        select(WhatsAppHandoff).where(
            WhatsAppHandoff.cart_id == order.cart_id,
            WhatsAppHandoff.kind == "cart_review",
        )
    )
    destination_was_confirmed = any(
        review.payload.get("destination_fingerprint") == destination_fingerprint
        for review in reviews
    )
    if not destination_was_confirmed:
        raise CommerceError(
            409,
            "WHATSAPP_DESTINATION_NOT_CONFIRMED",
            "The destination must match the explicitly confirmed cart-review destination",
        )
    key = f"confirmation:{order.id}:{order.provider_payment_id}:{destination_fingerprint}"
    share_text = (
        f"NiyamCart order {order.id[:8]}: Razorpay test payment was verified for "
        f"INR {order.total_paise / 100:,.2f}."
    )
    handoff = WhatsAppHandoff(
        cart_id=order.cart_id,
        order_id=order.id,
        kind="payment_confirmation",
        template_name=CONFIRMATION_TEMPLATE,
        idempotency_key=key,
        status="sending",
        payload={
            "share_text": share_text,
            "destination_fingerprint": destination_fingerprint,
            "permits_financial_approval": False,
        },
    )
    return _create_and_deliver(
        db,
        handoff=handoff,
        sender=sender,
        destination=request.destination,
        variables={"1": order.id[:8], "2": f"{order.total_paise / 100:.2f}"},
        audit_scope="order",
        audit_scope_id=order.id,
    )
