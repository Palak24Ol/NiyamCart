"""Read-only provider reconciliation; retries reuse the original approved provider order."""

from sqlalchemy.orm import Session

from .journey_service import fail, owned_order
from .razorpay_service import _reconcile_fetched_payment, create_razorpay_checkout, require_gateway


def reconcile_order(db: Session, customer_id: str, order_id: str, gateway) -> dict:
    order = owned_order(db, customer_id, order_id)
    if order.status == "paid":
        return {"status": "paid", "can_resume": False, "message": "Payment is verified."}
    gateway = require_gateway(gateway)
    if not order.provider_order_id:
        return {
            "status": "not_started",
            "can_resume": True,
            "message": "Provider checkout was not created. You can resume the same approved order.",
        }
    fetch = getattr(gateway, "fetch_order_payments", None)
    if fetch is None:
        fail(
            "RECONCILIATION_UNAVAILABLE", "This payment adapter does not support order lookup", 503
        )
    collection = fetch(order.provider_order_id)
    if not isinstance(collection, dict):
        fail("PAYMENT_LOOKUP_INCOMPLETE", "Payment lookup was incomplete; retry is blocked", 502)
    items = collection.get("items")
    if not isinstance(items, list) or collection.get("count") != len(items) or len(items) > 100:
        fail("PAYMENT_LOOKUP_INCOMPLETE", "Payment lookup was incomplete; retry is blocked", 502)
    for payment in items:
        if (
            not isinstance(payment, dict)
            or payment.get("order_id") != order.provider_order_id
            or not isinstance(payment.get("id"), str)
        ):
            fail("PAYMENT_LOOKUP_MISMATCH", "Payment data did not match this order", 502)
        if payment.get("status") == "captured":
            _, event = _reconcile_fetched_payment(
                db,
                order,
                gateway,
                payment["id"],
                "recovery:" + payment["id"],
                "recovery.provider_lookup",
            )
            if not event.accepted:
                fail("PAYMENT_NOT_VERIFIED", "Payment evidence did not match the approved order")
            return {
                "status": "paid",
                "can_resume": False,
                "message": "Payment recovered and independently verified. No new charge was made.",
            }
    if any(p.get("status") != "failed" for p in items):
        return {
            "status": "pending",
            "can_resume": False,
            "message": "A payment is unresolved. Wait for reconciliation before retrying.",
        }
    return {
        "status": "retry_available",
        "can_resume": True,
        "message": "No successful or unresolved payment was found. You may reopen the same "
        "approved order; no new order will be created.",
    }


def resume_order(db: Session, customer_id: str, order_id: str, gateway):
    result = reconcile_order(db, customer_id, order_id, gateway)
    if not result["can_resume"]:
        fail("PAYMENT_RETRY_BLOCKED", result["message"])
    return create_razorpay_checkout(db, order_id, gateway)
