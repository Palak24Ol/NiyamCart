from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .audit import append_audit
from .commerce_models import (
    Cart,
    CartCompatibilityClaim,
    CartItem,
    CartOfferSelection,
    Order,
    PaymentEvent,
)
from .commerce_schemas import CreateCartRequest, CreateOrderRequest
from .compatibility import complement_product_ids, products_by_category
from .models import Product

FREEZE_DURATION = timedelta(minutes=15)


class CommerceError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def load_cart(session: Session, cart_id: str) -> Cart:
    cart = session.scalar(
        select(Cart)
        .where(Cart.id == cart_id)
        .options(
            selectinload(Cart.items),
            selectinload(Cart.compatibility_claims),
            selectinload(Cart.fulfillment),
            selectinload(Cart.offer_selection),
            selectinload(Cart.intent_mandate),
        )
    )
    if cart is None:
        raise CommerceError(404, "CART_NOT_FOUND", "Cart not found")
    return cart


def create_cart(session: Session, request: CreateCartRequest) -> Cart:
    product_ids = [item.product_id for item in request.items]
    products = {
        product.id: product
        for product in session.scalars(select(Product).where(Product.id.in_(product_ids)))
    }
    missing = sorted(set(product_ids) - products.keys())
    if missing:
        raise CommerceError(404, "PRODUCT_NOT_FOUND", f"Unknown products: {', '.join(missing)}")

    cart_product_ids = set(product_ids)
    for claim in request.compatibility_claims:
        if {
            claim.primary_product_id,
            claim.addon_product_id,
        } - cart_product_ids:
            raise CommerceError(
                422,
                "INVALID_COMPATIBILITY_CLAIM",
                "Compatibility claims must reference products in the proposed cart",
            )
    if request.compatibility_claims:
        all_products = list(session.scalars(select(Product).order_by(Product.id)))
        by_category = products_by_category(all_products)
        for claim in request.compatibility_claims:
            primary = products[claim.primary_product_id]
            if claim.addon_product_id not in complement_product_ids(primary, by_category):
                raise CommerceError(
                    409,
                    "INCOMPATIBLE_ADDON",
                    f"{claim.addon_product_id} is not a verified add-on for "
                    f"{claim.primary_product_id}",
                )

    cart = Cart(
        id=str(uuid4()),
        status="proposed",
        currency="INR",
        subtotal_paise=0,
        total_paise=0,
    )
    for requested in request.items:
        product = products[requested.product_id]
        if requested.quantity > product.stock:
            raise CommerceError(
                409,
                "INSUFFICIENT_STOCK",
                f"Only {product.stock} units of {product.id} are available",
            )
        line_total = product.price_paise * requested.quantity
        cart.items.append(
            CartItem(
                product_id=product.id,
                product_name=product.name,
                product_version=product.version,
                quantity=requested.quantity,
                unit_price_paise=product.price_paise,
                line_total_paise=line_total,
            )
        )
        cart.subtotal_paise += line_total
    for claim in request.compatibility_claims:
        cart.compatibility_claims.append(
            CartCompatibilityClaim(
                primary_product_id=claim.primary_product_id,
                addon_product_id=claim.addon_product_id,
                rule_id="COMPAT-DETERMINISTIC-COMPLEMENT-V1",
            )
        )
    cart.total_paise = cart.subtotal_paise
    session.add(cart)
    append_audit(
        session,
        "cart",
        cart.id,
        "cart_proposed",
        {
            "currency": cart.currency,
            "total_paise": cart.total_paise,
            "items": [
                {"product_id": item.product_id, "quantity": item.quantity} for item in cart.items
            ],
            "compatibility_claims": [
                {
                    "primary_product_id": claim.primary_product_id,
                    "addon_product_id": claim.addon_product_id,
                    "rule_id": claim.rule_id,
                }
                for claim in cart.compatibility_claims
            ],
        },
    )
    session.commit()
    return load_cart(session, cart.id)


def _cart_validation_error(session: Session, cart: Cart) -> CommerceError | None:
    products = {
        product.id: product
        for product in session.scalars(
            select(Product).where(Product.id.in_([item.product_id for item in cart.items]))
        )
    }
    for item in cart.items:
        product = products.get(item.product_id)
        if (
            product is None
            or product.version != item.product_version
            or product.price_paise != item.unit_price_paise
        ):
            return CommerceError(409, "CART_CHANGED", "Product or price changed; rebuild the cart")
        if product.stock < item.quantity:
            return CommerceError(
                409,
                "CART_INVENTORY_CHANGED",
                f"Only {product.stock} units of {item.product_id} remain; rebuild the cart",
            )

    if cart.compatibility_claims:
        all_products = list(session.scalars(select(Product).order_by(Product.id)))
        by_category = products_by_category(all_products)
        for claim in cart.compatibility_claims:
            primary = products.get(claim.primary_product_id)
            if primary is None or claim.addon_product_id not in complement_product_ids(
                primary, by_category
            ):
                return CommerceError(
                    409,
                    "CART_COMPATIBILITY_CHANGED",
                    "A claimed add-on is no longer compatible; rebuild the cart",
                )
    return None


def _invalidate_if_changed(session: Session, cart: Cart) -> None:
    error = _cart_validation_error(session, cart)
    if error is not None:
        cart.status = "invalidated"
        append_audit(
            session,
            "cart",
            cart.id,
            "cart_invalidated",
            {"error": error.code, "message": error.message},
        )
        session.commit()
        raise error


def _invalidate_if_hash_changed(session: Session, cart: Cart) -> None:
    recalculated = hashlib.sha256(canonical_cart(cart)).hexdigest()
    if not cart.cart_hash or recalculated != cart.cart_hash:
        cart.status = "invalidated"
        append_audit(
            session,
            "cart",
            cart.id,
            "cart_invalidated",
            {"error": "CART_MUTATED", "recalculated_hash": recalculated},
        )
        session.commit()
        raise CommerceError(
            409,
            "CART_MUTATED",
            "The frozen cart changed after review; rebuild and approve it again",
        )


def canonical_cart(cart: Cart) -> bytes:
    fulfillment = cart.fulfillment
    offer = cart.offer_selection
    mandate = cart.intent_mandate
    payload = {
        "cart_id": cart.id,
        "currency": cart.currency,
        "items": [
            {
                "product_id": item.product_id,
                "product_version": item.product_version,
                "quantity": item.quantity,
                "unit_price_paise": item.unit_price_paise,
                "line_total_paise": item.line_total_paise,
            }
            for item in sorted(cart.items, key=lambda value: value.product_id)
        ],
        "compatibility_claims": [
            {
                "primary_product_id": claim.primary_product_id,
                "addon_product_id": claim.addon_product_id,
                "rule_id": claim.rule_id,
            }
            for claim in sorted(
                cart.compatibility_claims,
                key=lambda value: (value.primary_product_id, value.addon_product_id),
            )
        ],
        "subtotal_paise": cart.subtotal_paise,
        "total_paise": cart.total_paise,
        "fulfillment": None
        if fulfillment is None
        else {
            "address_fingerprint": fulfillment.address_fingerprint,
            "address_label": fulfillment.address_label,
            "city": fulfillment.city,
            "pincode": fulfillment.pincode,
            "delivery_paise": fulfillment.delivery_paise,
            "eta_min_days": fulfillment.eta_min_days,
            "eta_max_days": fulfillment.eta_max_days,
        },
        "payment_offer": None
        if offer is None
        else {
            "offer_key": offer.offer_key,
            "provider_offer_id": offer.provider_offer_id,
            "payment_method": offer.payment_method,
            "savings_paise": offer.savings_paise,
            "expected_payable_paise": offer.expected_payable_paise,
        },
        "intent_mandate": None
        if mandate is None
        else {
            "mandate_id": mandate.mandate_id,
            "integrity_hash": mandate.integrity_hash,
            "constraints_json": mandate.constraints_json,
            "payment_rule": mandate.payment_rule,
            "max_addons": mandate.max_addons,
            "expires_at": mandate.expires_at.isoformat(),
        },
        "version": cart.version,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def freeze_cart(
    session: Session,
    cart_id: str,
    now: datetime | None = None,
    *,
    require_checkout_context: bool = False,
) -> Cart:
    now = now or utc_now()
    cart = load_cart(session, cart_id)
    if cart.status == "frozen" and cart.expires_at and cart.expires_at > now:
        _invalidate_if_changed(session, cart)
        _invalidate_if_hash_changed(session, cart)
        return cart
    if cart.status != "proposed":
        raise CommerceError(409, "INVALID_CART_STATE", f"Cannot freeze a {cart.status} cart")
    _invalidate_if_changed(session, cart)
    if require_checkout_context and cart.fulfillment is None:
        raise CommerceError(409, "DELIVERY_REQUIRED", "Confirm a delivery address first")
    if require_checkout_context and cart.offer_selection is None:
        raise CommerceError(409, "PAYMENT_OFFER_REQUIRED", "Choose a payment option first")
    if cart.intent_mandate is not None:
        if cart.intent_mandate.expires_at <= now:
            raise CommerceError(
                409, "INTENT_MANDATE_EXPIRED", "The shopping intent expired; ask Niyam again"
            )
        constraints = json.loads(cart.intent_mandate.constraints_json)
        maximum_paise = constraints.get("maximum_price_paise")
        if isinstance(maximum_paise, int) and cart.total_paise > maximum_paise:
            raise CommerceError(
                409,
                "INTENT_BUDGET_EXCEEDED",
                "The final delivered total exceeds the signed buyer budget",
            )
        if len(cart.compatibility_claims) > cart.intent_mandate.max_addons:
            raise CommerceError(
                409,
                "INTENT_ADDON_LIMIT_EXCEEDED",
                "The cart contains more add-ons than the signed buyer intent permits",
            )

    cart.cart_hash = hashlib.sha256(canonical_cart(cart)).hexdigest()
    cart.status = "frozen"
    cart.frozen_at = now
    cart.expires_at = now + FREEZE_DURATION
    append_audit(
        session,
        "cart",
        cart.id,
        "cart_frozen",
        {
            "cart_hash": cart.cart_hash,
            "total_paise": cart.total_paise,
            "expires_at": cart.expires_at.isoformat(),
        },
    )
    session.commit()
    return load_cart(session, cart.id)


def approve_cart(
    session: Session,
    cart_id: str,
    supplied_hash: str,
    now: datetime | None = None,
) -> Cart:
    now = now or utc_now()
    cart = load_cart(session, cart_id)
    if cart.status != "frozen":
        raise CommerceError(409, "INVALID_CART_STATE", f"Cannot approve a {cart.status} cart")
    if not cart.expires_at or cart.expires_at <= now:
        cart.status = "expired"
        append_audit(session, "cart", cart.id, "cart_expired", {})
        session.commit()
        raise CommerceError(409, "CART_EXPIRED", "The frozen cart expired; review it again")
    _invalidate_if_changed(session, cart)
    _invalidate_if_hash_changed(session, cart)
    if not cart.cart_hash or supplied_hash != cart.cart_hash:
        raise CommerceError(409, "CART_HASH_MISMATCH", "Approval does not match the frozen cart")

    cart.status = "approved"
    cart.approved_at = now
    append_audit(
        session,
        "cart",
        cart.id,
        "cart_approved",
        {"cart_hash": cart.cart_hash, "approved_at": now.isoformat()},
    )
    session.commit()
    return load_cart(session, cart.id)


def create_order(
    session: Session,
    request: CreateOrderRequest,
    now: datetime | None = None,
) -> Order:
    now = now or utc_now()
    existing = session.scalar(select(Order).where(Order.idempotency_key == request.idempotency_key))
    if existing:
        if existing.cart_id != request.cart_id or existing.cart_hash != request.cart_hash:
            raise CommerceError(
                409,
                "IDEMPOTENCY_KEY_REUSED",
                "This idempotency key belongs to a different order request",
            )
        return existing

    cart = load_cart(session, request.cart_id)
    if cart.status != "approved":
        if cart.status == "ordered":
            session.rollback()
            recovered = session.scalar(
                select(Order).where(Order.idempotency_key == request.idempotency_key)
            )
            if (
                recovered
                and recovered.cart_id == request.cart_id
                and recovered.cart_hash == request.cart_hash
            ):
                return recovered
        raise CommerceError(409, "INVALID_CART_STATE", f"Cannot order a {cart.status} cart")
    if not cart.expires_at or cart.expires_at <= now:
        cart.status = "expired"
        append_audit(session, "cart", cart.id, "cart_expired", {})
        session.commit()
        raise CommerceError(409, "CART_EXPIRED", "The approved cart expired")
    if not cart.cart_hash or cart.cart_hash != request.cart_hash:
        raise CommerceError(409, "CART_HASH_MISMATCH", "Order does not match the approved cart")
    _invalidate_if_changed(session, cart)
    _invalidate_if_hash_changed(session, cart)

    claimed = session.execute(
        update(Cart)
        .where(Cart.id == cart.id, Cart.status == "approved", Cart.version == cart.version)
        .values(status="ordered", version=Cart.version + 1)
    )
    if claimed.rowcount != 1:
        session.rollback()
        recovered = session.scalar(
            select(Order).where(Order.idempotency_key == request.idempotency_key)
        )
        if (
            recovered
            and recovered.cart_id == request.cart_id
            and recovered.cart_hash == request.cart_hash
        ):
            return recovered
        raise CommerceError(409, "ORDER_ALREADY_CLAIMED", "Another request claimed this cart")

    order = Order(
        id=str(uuid4()),
        cart_id=cart.id,
        idempotency_key=request.idempotency_key,
        status="payment_pending",
        currency=cart.currency,
        total_paise=cart.total_paise,
        cart_hash=cart.cart_hash,
    )
    session.add(order)
    append_audit(
        session,
        "cart",
        cart.id,
        "order_claimed",
        {"order_id": order.id, "cart_hash": order.cart_hash},
    )
    append_audit(
        session,
        "order",
        order.id,
        "order_created",
        {
            "cart_id": order.cart_id,
            "cart_hash": order.cart_hash,
            "currency": order.currency,
            "total_paise": order.total_paise,
            "status": order.status,
        },
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        recovered = session.scalar(
            select(Order).where(Order.idempotency_key == request.idempotency_key)
        )
        if recovered and recovered.cart_id == request.cart_id:
            return recovered
        raise CommerceError(409, "ORDER_CONFLICT", "The cart already has an order") from None
    return order


def bind_provider_order(session: Session, order_id: str, provider_order_id: str) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise CommerceError(404, "ORDER_NOT_FOUND", "Order not found")
    if order.status != "payment_pending":
        raise CommerceError(409, "INVALID_ORDER_STATE", "Only pending orders can be bound")
    if order.provider_order_id and order.provider_order_id != provider_order_id:
        raise CommerceError(409, "PROVIDER_ORDER_MISMATCH", "Provider order is already bound")
    order.provider_order_id = provider_order_id
    append_audit(
        session,
        "order",
        order.id,
        "provider_order_bound",
        {"provider_order_id": provider_order_id},
    )
    session.commit()
    return order


@dataclass(frozen=True)
class PaymentEvidence:
    provider_event_id: str
    event_type: str
    provider_order_id: str
    provider_payment_id: str
    amount_paise: int
    currency: str
    signature_verified: bool
    captured: bool
    provider_offer_id: str | None = None


def finalise_payment(
    session: Session,
    order_id: str,
    evidence: PaymentEvidence,
    now: datetime | None = None,
) -> tuple[Order, PaymentEvent]:
    now = now or utc_now()
    duplicate = session.get(PaymentEvent, evidence.provider_event_id)
    if duplicate:
        return duplicate.order, duplicate

    order = session.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise CommerceError(404, "ORDER_NOT_FOUND", "Order not found")

    evidence_payload = json.dumps(evidence.__dict__, sort_keys=True, separators=(",", ":"))
    payload_hash = hashlib.sha256(evidence_payload.encode()).hexdigest()
    accepted = False
    reason = "verification_failed"
    selected_offer = session.get(CartOfferSelection, order.cart_id)
    expected_amount = (
        selected_offer.expected_payable_paise
        if selected_offer and selected_offer.provider_offer_id
        else order.total_paise
    )
    expected_offer_id = selected_offer.provider_offer_id if selected_offer else None

    if not evidence.signature_verified:
        reason = "signature_invalid"
    elif not evidence.captured:
        reason = "payment_not_captured"
    elif order.provider_order_id != evidence.provider_order_id:
        reason = "provider_order_mismatch"
    elif expected_amount != evidence.amount_paise or order.currency != evidence.currency:
        reason = "amount_or_currency_mismatch"
    elif expected_offer_id != evidence.provider_offer_id:
        reason = "offer_mismatch"
    elif order.status == "paid" and order.provider_payment_id == evidence.provider_payment_id:
        accepted = True
        reason = "already_finalised"
    elif order.status != "payment_pending":
        reason = "invalid_order_state"
    else:
        result = session.execute(
            update(Order)
            .where(Order.id == order.id, Order.status == "payment_pending")
            .values(
                status="paid",
                provider_payment_id=evidence.provider_payment_id,
                paid_at=now,
            )
        )
        accepted = result.rowcount == 1
        reason = "verified" if accepted else "already_claimed"

    event = PaymentEvent(
        provider_event_id=evidence.provider_event_id,
        order_id=order.id,
        event_type=evidence.event_type,
        accepted=accepted,
        reason=reason,
        payload_hash=payload_hash,
    )
    session.add(event)
    append_audit(
        session,
        "order",
        order.id,
        "payment_evidence_evaluated",
        {
            "provider_event_id": evidence.provider_event_id,
            "event_type": evidence.event_type,
            "provider_order_id": evidence.provider_order_id,
            "provider_payment_id": evidence.provider_payment_id,
            "amount_paise": evidence.amount_paise,
            "currency": evidence.currency,
            "captured": evidence.captured,
            "provider_offer_id": evidence.provider_offer_id,
            "accepted": accepted,
            "reason": reason,
            "resulting_status": "paid" if accepted else order.status,
        },
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        duplicate = session.get(PaymentEvent, evidence.provider_event_id)
        if duplicate:
            return duplicate.order, duplicate
        raise
    return session.get(Order, order.id), event
