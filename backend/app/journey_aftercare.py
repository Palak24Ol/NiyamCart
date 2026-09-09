from __future__ import annotations

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .audit import append_audit
from .commerce import load_cart, utc_now
from .commerce_models import Order
from .journey_models import JourneyCart, ShipmentEvent, SupportCase
from .journey_schemas import ShipmentInput, SupportInput
from .journey_service import fail, owned, owned_order, product_data
from .journey_tasks import notify
from .models import Product


def shipment_events(db: Session, order_id: str) -> list[ShipmentEvent]:
    events = list(
        db.scalars(
            select(ShipmentEvent)
            .where(ShipmentEvent.order_id == order_id)
            .order_by(ShipmentEvent.occurred_at)
        )
    )
    verified = [event for event in events if event.source == "merchant_webhook"]
    return verified or events


def order_data(db: Session, order: Order) -> dict:
    cart = load_cart(db, order.cart_id)
    events = shipment_events(db, order.id)
    latest = events[-1] if events else None
    delivery = next((e for e in reversed(events) if e.status == "delivered"), None)
    eta = None
    if cart.fulfillment and order.paid_at:
        eta = (order.paid_at + timedelta(days=cart.fulfillment.eta_max_days)).isoformat()
    is_late = bool(eta and not delivery and datetime.fromisoformat(eta) < utc_now())
    items = []
    for item in cart.items:
        product = db.get(Product, item.product_id)
        window = product.return_window_days if product else 0
        end = delivery.occurred_at + timedelta(days=window) if delivery else None
        items.append(
            {
                "productId": item.product_id,
                "name": item.product_name,
                "image": product.image if product else "",
                "quantity": item.quantity,
                "unitPricePaise": item.unit_price_paise,
                "return_window_days": window,
                "return_eligible": bool(
                    order.status == "paid" and end and window > 0 and utc_now() <= end
                ),
                "return_deadline": end.isoformat() if end else None,
            }
        )
    return {
        "orderId": order.id,
        "cartId": order.cart_id,
        "status": order.status,
        "amountPaise": order.total_paise,
        "currency": order.currency,
        "paymentId": order.provider_payment_id,
        "verifiedAt": order.paid_at,
        "createdAt": order.created_at,
        "cartHash": order.cart_hash,
        "testMode": True,
        "items": items,
        "shipment_status": latest.status if latest else "awaiting_carrier",
        "shipment_source": latest.source if latest else "not_connected",
        "estimated_arrival": eta,
        "is_late": is_late,
        "events": [
            {
                "id": e.id,
                "status": e.status,
                "detail": e.detail,
                "source": e.source,
                "occurred_at": e.occurred_at,
            }
            for e in events
        ],
        "policy_source": "current_merchant_catalogue",
        "cases": [
            case_data(case)
            for case in db.scalars(
                select(SupportCase)
                .where(SupportCase.order_id == order.id)
                .order_by(SupportCase.created_at.desc())
            )
        ],
    }


def case_data(case: SupportCase) -> dict:
    return {
        "id": case.id,
        "order_id": case.order_id,
        "kind": case.kind,
        "status": case.status,
        "details": case.details,
        "created_at": case.created_at,
    }


def prepare_case(
    db: Session, customer_id: str, order_id: str, payload: SupportInput
) -> SupportCase:
    order = owned_order(db, customer_id, order_id)
    existing = db.scalar(
        select(SupportCase).where(
            SupportCase.customer_id == customer_id, SupportCase.request_key == payload.request_key
        )
    )
    if existing:
        if (
            existing.order_id != order_id
            or existing.kind != payload.kind
            or any(
                existing.details.get(key) != getattr(payload, key)
                for key in ("message", "product_id", "replacement_product_id")
            )
        ):
            fail("REQUEST_KEY_REUSED", "Use a new request key for a different support request")
        return existing
    if (
        len(
            list(
                db.scalars(
                    select(SupportCase.id).where(
                        SupportCase.customer_id == customer_id,
                        SupportCase.status.in_(["draft", "awaiting_merchant"]),
                    )
                )
            )
        )
        >= 50
    ):
        fail("CASE_LIMIT", "Please resolve existing cases before opening more")
    details = payload.model_dump(exclude={"request_key", "kind"})
    details["data_mode"] = "test_mode"
    if payload.kind in {"return", "exchange"}:
        summary = order_data(db, order)
        item = next((p for p in summary["items"] if p["productId"] == payload.product_id), None)
        if not item or not item["return_eligible"]:
            fail(
                "RETURN_NOT_ELIGIBLE",
                "This item needs verified delivery and an open return "
                "window. Open a support case if you need help",
            )
        details.update(
            {
                "quantity": item["quantity"],
                "estimated_refund_paise": item["unitPricePaise"] * item["quantity"],
                "policy_source": summary["policy_source"],
                "delivery_source": summary["shipment_source"],
                "refund_status": "not_requested",
                "shipping_refund_included": False,
            }
        )
        if payload.kind == "exchange":
            original = db.get(Product, payload.product_id)
            replacement = db.get(Product, payload.replacement_product_id)
            if not replacement or replacement.stock < item["quantity"]:
                fail("REPLACEMENT_UNAVAILABLE", "Choose an in-stock replacement")
            if replacement.id == original.id or replacement.category != original.category:
                fail(
                    "INVALID_REPLACEMENT",
                    "Choose a different item in the same category. "
                    "Size-specific stock is not available in this catalogue",
                )
            details["replacement"] = product_data(replacement)
            details["price_difference_paise"] = (
                replacement.price_paise - item["unitPricePaise"]
            ) * item["quantity"]
    case = SupportCase(
        id=str(uuid4()),
        customer_id=customer_id,
        order_id=order_id,
        kind=payload.kind,
        status="draft",
        request_key=payload.request_key,
        details=details,
    )
    db.add(case)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        repeated = db.scalar(
            select(SupportCase).where(
                SupportCase.customer_id == customer_id,
                SupportCase.request_key == payload.request_key,
            )
        )
        if repeated is None:
            raise
        return prepare_case(db, customer_id, order_id, payload)
    append_audit(
        db,
        "order",
        order.id,
        "support_draft_prepared",
        {"case_id": case.id, "kind": case.kind, "financial_action": False},
    )
    db.commit()
    return case


def confirm_case(db: Session, customer_id: str, identity: str) -> SupportCase:
    case = owned(db, SupportCase, identity, customer_id)
    if case.status == "awaiting_merchant":
        return case
    if case.status != "draft":
        fail("CASE_CLOSED", "This case cannot be submitted")
    # Serialize all item claims on the order, including concurrent return/exchange submissions.
    db.execute(update(Order).where(Order.id == case.order_id).values(status=Order.status))
    if case.kind in {"return", "exchange"}:
        order = owned_order(db, customer_id, case.order_id)
        summary = order_data(db, order)
        item = next(p for p in summary["items"] if p["productId"] == case.details["product_id"])
        if not item["return_eligible"]:
            fail("RETURN_WINDOW_CLOSED", "The return window closed before confirmation")
        others = list(
            db.scalars(
                select(SupportCase).where(
                    SupportCase.order_id == case.order_id,
                    SupportCase.id != case.id,
                    SupportCase.kind.in_(["return", "exchange"]),
                    SupportCase.status == "awaiting_merchant",
                )
            )
        )
        if any(other.details["product_id"] == case.details["product_id"] for other in others):
            fail("ITEM_ALREADY_CLAIMED", "A return or exchange already exists for this item")
        if case.kind == "exchange":
            current = db.get(Product, case.details["replacement_product_id"])
            if (
                not current
                or current.stock < item["quantity"]
                or (current.price_paise != case.details["replacement"]["price_paise"])
            ):
                fail(
                    "EXCHANGE_CHANGED", "The replacement price or stock changed. Prepare a new case"
                )
    case.status = "awaiting_merchant"
    case.details = {
        **case.details,
        "submitted_at": utc_now().isoformat(),
        "fulfillment_status": "awaiting_merchant_review",
    }
    append_audit(
        db,
        "order",
        case.order_id,
        "support_case_submitted",
        {"case_id": case.id, "kind": case.kind, "financial_action": False},
    )
    db.commit()
    return case


def record_shipment(db: Session, payload: ShipmentInput, source: str) -> ShipmentEvent:
    order = db.get(Order, payload.order_id)
    if not order or order.status != "paid":
        fail("PAID_ORDER_REQUIRED", "Shipment events require a verified paid order")
    when = payload.occurred_at
    when = when.replace(tzinfo=UTC) if when.tzinfo is None else when.astimezone(UTC)
    when = when.replace(tzinfo=None)
    if when > utc_now() + timedelta(minutes=5) or (order.paid_at and when < order.paid_at):
        fail("INVALID_EVENT_TIME", "Shipment time must follow payment and cannot be in the future")
    identity = ("demo:" if source == "demo_simulation" else "merchant:") + payload.event_id
    prior = db.get(ShipmentEvent, identity)
    if prior:
        if (prior.order_id, prior.status, prior.detail, prior.occurred_at) != (
            order.id,
            payload.status,
            payload.detail,
            when,
        ):
            fail("EVENT_ID_REUSED", "The shipment event ID was reused with different data")
        return prior
    db.execute(update(Order).where(Order.id == order.id).values(status=Order.status))
    db.expire_all()
    if db.get(ShipmentEvent, identity):
        return record_shipment(db, payload, source)
    previous = shipment_events(db, order.id)
    if source == "demo_simulation" and any(e.source == "merchant_webhook" for e in previous):
        fail("VERIFIED_TRACKING_EXISTS", "Simulation cannot replace merchant tracking")
    same_source = [e for e in previous if e.source == source]
    if same_source:
        last = same_source[-1]
        if when <= last.occurred_at:
            fail("STALE_SHIPMENT_EVENT", "Shipment events must move forward in time")
        if last.status == "delivered":
            fail("SHIPMENT_COMPLETE", "A delivered shipment cannot move backwards")
        ranks = {"confirmed": 0, "shipped": 1, "out_for_delivery": 2, "delivered": 3}
        prior_rank = max((ranks.get(e.status, 0) for e in same_source), default=0)
        if payload.status != "delayed" and ranks[payload.status] < prior_rank:
            fail("SHIPMENT_REGRESSION", "Shipment progress cannot move backwards")
    event = ShipmentEvent(
        id=identity,
        order_id=order.id,
        status=payload.status,
        source=source,
        detail=payload.detail,
        occurred_at=when,
    )
    db.add(event)
    cart = load_cart(db, order.cart_id)
    link = db.get(JourneyCart, cart.id)
    owner = (
        link.customer_id if link else (cart.fulfillment.customer_id if cart.fulfillment else None)
    )
    if owner:
        notify(
            db,
            owner,
            identity,
            "Delivery update: " + payload.status.replace("_", " "),
            ("TEST SIMULATION: " if source == "demo_simulation" else "") + payload.detail,
            "/orders?order=" + order.id,
        )
    append_audit(
        db,
        "order",
        order.id,
        "shipment_event",
        {"event_id": identity, "status": payload.status, "source": source},
    )
    db.commit()
    return event


def verify_shipment_signature(body: bytes, timestamp: str, signature: str):
    secret = os.getenv("MERCHANT_FULFILLMENT_WEBHOOK_SECRET", "")
    if len(secret) < 32:
        fail("FULFILLMENT_NOT_CONFIGURED", "Merchant tracking webhook is not configured", 503)
    try:
        if abs(datetime.now(UTC).timestamp() - int(timestamp)) > 300:
            raise ValueError
    except ValueError:
        fail("STALE_SIGNATURE", "A fresh webhook timestamp is required", 401)
    expected = hmac.new(
        secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        fail("INVALID_SIGNATURE", "Invalid merchant webhook signature", 401)


def answer_order_question(db: Session, customer_id: str, order_id: str, message: str) -> dict:
    summary = order_data(db, owned_order(db, customer_id, order_id))
    text = message.casefold()
    # Deterministic tool routing is the offline path; it makes no delivery or refund claims.
    if any(word in text for word in ("invoice", "receipt", "bill")):
        return {
            "answer": "Your verified payment receipt is available below. A tax invoice "
            "must be issued by the merchant.",
            "action": "receipt",
            "mode": "verified_rules",
        }
    if any(word in text for word in ("return", "exchange", "small", "large", "refund")):
        eligible = [i["name"] for i in summary["items"] if i["return_eligible"]]
        return {
            "answer": "Choose an eligible item to prepare a return or exchange request. "
            "The merchant must review it before any refund or replacement."
            if eligible
            else "No item currently has both recorded delivery and an open return window. "
            "You can open a support case for the merchant.",
            "action": "return_options",
            "mode": "verified_rules",
        }
    if any(word in text for word in ("broken", "damaged", "help", "support", "cancel")):
        case = prepare_case(
            db,
            customer_id,
            order_id,
            SupportInput(
                kind="support",
                message=message,
                request_key="question-"
                + hashlib.sha256((order_id + message).encode()).hexdigest()[:40],
            ),
        )
        return {
            "answer": "I prepared a support case with your order details. Review and submit "
            "it below; the merchant has not acted on it yet.",
            "action": "case",
            "case": case_data(case),
            "mode": "verified_rules",
        }
    latest = summary["events"][-1] if summary["events"] else None
    return {
        "answer": (
            ("Simulation: " if latest["source"] == "demo_simulation" else "") + latest["detail"]
        )
        if latest
        else "Payment status: " + summary["status"] + ". Carrier tracking has not arrived yet. "
        "Any delivery date shown is a catalogue estimate.",
        "action": "tracking",
        "mode": "verified_rules",
    }


def payment_receipt(db: Session, customer_id: str, order_id: str) -> str:
    order = owned_order(db, customer_id, order_id)
    if order.status != "paid":
        fail("PAYMENT_NOT_VERIFIED", "A receipt is available only after verified payment")
    cart = load_cart(db, order.cart_id)
    lines = [
        "NIYAMCART — VERIFIED TEST PAYMENT RECEIPT",
        "Not a tax invoice. No real money charged.",
        f"Order: {order.id}",
        f"Razorpay test payment: {order.provider_payment_id}",
        f"Verified: {order.paid_at} UTC",
        f"Total: INR {order.total_paise / 100:.2f}",
        "",
    ]
    lines += [
        f"{i.product_name} x {i.quantity}: INR {i.line_total_paise / 100:.2f}" for i in cart.items
    ]
    return "\n".join(lines + ["", f"Exact cart hash: {order.cart_hash}"])
