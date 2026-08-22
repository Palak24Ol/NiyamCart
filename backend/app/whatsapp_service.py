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
from .whatsapp_models import WhatsAppHandoff, WhatsAppOptIn
from .whatsapp_schemas import WhatsAppHandoffResponse, WhatsAppReviewRequest

CONSENT_VERSION = "whatsapp-review-v1"
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


def _existing(db: Session, key: str) -> WhatsAppHandoff | None:
    return db.scalar(
        select(WhatsAppHandoff).where(WhatsAppHandoff.idempotency_key == key)
    )


def _response(handoff: WhatsAppHandoff, *, duplicate: bool) -> WhatsAppHandoffResponse:
    return WhatsAppHandoffResponse(
        status="ready_for_user_share",
        duplicate=duplicate,
        template_name=handoff.template_name,
        review_url=(
            str(handoff.payload.get("review_url"))
            if handoff.payload.get("review_url")
            else None
        ),
        share_text=str(handoff.payload["share_text"]),
        message=(
            "Copy this utility message into WhatsApp yourself. It cannot approve or pay."
        ),
    )


def prepare_cart_review_handoff(
    db: Session,
    cart_id: str,
    request: WhatsAppReviewRequest,
    settings: WhatsAppSettings,
) -> WhatsAppHandoffResponse:
    if not settings.enabled:
        return WhatsAppHandoffResponse(
            status="disabled",
            duplicate=False,
            template_name=None,
            review_url=None,
            share_text=None,
            message="WhatsApp handoff is disabled; continue with the in-app exact-cart review.",
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
    key = f"review:{cart.id}:{cart.cart_hash}"
    existing = _existing(db, key)
    if existing is not None:
        return _response(existing, duplicate=True)
    handoff = WhatsAppHandoff(
        cart_id=cart.id,
        kind="cart_review",
        template_name=REVIEW_TEMPLATE,
        idempotency_key=key,
        status="ready_for_user_share",
        payload={
            "review_url": review_url,
            "share_text": (
                f"NiyamCart cart {cart.id[:8]} totals INR {cart.total_paise / 100:,.2f}. "
                f"Review it here: {review_url}. Approval and payment happen only in NiyamCart."
            ),
            "permits_financial_approval": False,
        },
    )
    db.add(handoff)
    append_audit(
        db,
        "cart",
        cart.id,
        "whatsapp_review_handoff_prepared",
        {"template_name": REVIEW_TEMPLATE, "permits_financial_approval": False},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _existing(db, key)
        if existing is None:
            raise
        return _response(existing, duplicate=True)
    return _response(handoff, duplicate=False)


def prepare_payment_confirmation_handoff(
    db: Session,
    order_id: str,
    settings: WhatsAppSettings,
) -> WhatsAppHandoffResponse:
    if not settings.enabled:
        return WhatsAppHandoffResponse(
            status="disabled",
            duplicate=False,
            template_name=None,
            review_url=None,
            share_text=None,
            message="WhatsApp handoff is disabled; the in-app verified state remains available.",
        )
    order = db.get(Order, order_id)
    if order is None:
        raise CommerceError(404, "ORDER_NOT_FOUND", "Order not found")
    if order.status != "paid" or not order.provider_payment_id:
        raise CommerceError(
            409,
            "PAYMENT_NOT_VERIFIED",
            "A confirmation can be prepared only after backend payment verification",
        )
    if db.get(WhatsAppOptIn, order.cart_id) is None:
        raise CommerceError(409, "WHATSAPP_NOT_OPTED_IN", "The buyer did not opt in")
    key = f"confirmation:{order.id}:{order.provider_payment_id}"
    existing = _existing(db, key)
    if existing is not None:
        return _response(existing, duplicate=True)
    handoff = WhatsAppHandoff(
        cart_id=order.cart_id,
        order_id=order.id,
        kind="payment_confirmation",
        template_name=CONFIRMATION_TEMPLATE,
        idempotency_key=key,
        status="ready_for_user_share",
        payload={
            "share_text": (
                f"NiyamCart order {order.id[:8]}: Razorpay test payment was verified for "
                f"INR {order.total_paise / 100:,.2f}."
            )
        },
    )
    db.add(handoff)
    append_audit(
        db,
        "order",
        order.id,
        "whatsapp_confirmation_handoff_prepared",
        {"template_name": CONFIRMATION_TEMPLATE, "payment_verified": True},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _existing(db, key)
        if existing is None:
            raise
        return _response(existing, duplicate=True)
    return _response(handoff, duplicate=False)
