from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .audit import append_audit
from .commerce import load_cart, utc_now
from .commerce_models import Cart, Order
from .commerce_schemas import CartItemInput
from .journey_models import JourneyCart, JourneyNotice, JourneyTask
from .journey_schemas import TaskInput
from .journey_service import (
    bind_cart,
    fail,
    owned,
    owned_cart,
    owned_order,
    product_data,
    quote_products,
)
from .models import Product

logger = logging.getLogger(__name__)


def notify(db: Session, customer_id: str, key: str, title: str, body: str, href: str):
    if db.scalar(
        select(JourneyNotice.id).where(
            JourneyNotice.customer_id == customer_id, JourneyNotice.dedupe_key == key
        )
    ):
        return
    db.add(
        JourneyNotice(
            id=str(uuid4()),
            customer_id=customer_id,
            dedupe_key=key,
            title=title,
            body=body,
            href=href,
        )
    )


def task_data(task: JourneyTask) -> dict:
    return {
        "id": task.id,
        "kind": task.kind,
        "status": task.status,
        "settings": task.settings,
        "result": task.result,
        "next_run": task.next_run,
        "expires_at": task.expires_at,
        "failures": task.failures,
        "created_at": task.created_at,
    }


def create_task(db: Session, customer_id: str, payload: TaskInput) -> JourneyTask:
    if not payload.consent:
        fail("CONSENT_REQUIRED", "Enable monitoring to create this task", 422)
    data = payload.model_dump(mode="json")
    if payload.kind == "watch":
        product = db.get(Product, payload.product_id)
        if not product:
            fail("PRODUCT_NOT_FOUND", "Choose a catalogue product", 404)
        data["product_name"] = product.name
        if payload.target_paise is None:
            data["target_paise"] = quote_products([product])["total_paise"]
    elif payload.kind == "replenish":
        order = owned_order(db, customer_id, payload.order_id or "")
        if order.status != "paid":
            fail("PAYMENT_REQUIRED", "Reorder reminders require a verified paid order")
        data["baseline_paise"] = order.total_paise
    else:
        cart = owned_cart(db, customer_id, payload.cart_id or "")
        data["baseline_paise"] = cart.total_paise
    dedupe = hashlib.sha256(
        json.dumps(
            {
                k: data[k]
                for k in (
                    "kind",
                    "product_id",
                    "order_id",
                    "cart_id",
                    "target_paise",
                    "interval_days",
                )
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    existing = db.scalar(
        select(JourneyTask).where(
            JourneyTask.customer_id == customer_id, JourneyTask.dedupe_key == dedupe
        )
    )
    if existing:
        if existing.status in {"completed", "cancelled", "expired"}:
            existing.status = "active"
            existing.result = {}
            existing.settings = data
            existing.failures = 0
            existing.expires_at = payload.expires_at
            existing.next_run = utc_now() + (
                timedelta(days=payload.interval_days)
                if payload.kind == "replenish"
                else timedelta()
            )
            if existing.next_run >= existing.expires_at:
                fail("EXPIRY_TOO_SOON", "Expiry must be after the first scheduled check", 422)
            append_audit(db, "journey_task", existing.id, "task_restarted", {"kind": existing.kind})
            db.commit()
        return existing
    count = len(
        list(
            db.scalars(
                select(JourneyTask.id).where(
                    JourneyTask.customer_id == customer_id,
                    JourneyTask.status.in_(["active", "awaiting_review", "paused"]),
                )
            )
        )
    )
    if count >= 50:
        fail("TASK_LIMIT", "You can keep up to 50 active or paused tasks")
    now = utc_now()
    task = JourneyTask(
        id=str(uuid4()),
        customer_id=customer_id,
        kind=payload.kind,
        dedupe_key=dedupe,
        settings=data,
        result={},
        status="active",
        next_run=now
        + (timedelta(days=payload.interval_days) if payload.kind == "replenish" else timedelta()),
        expires_at=payload.expires_at,
    )
    if task.next_run >= task.expires_at:
        fail("EXPIRY_TOO_SOON", "Task expiry must be after its first scheduled check", 422)
    db.add(task)
    try:
        db.flush()
        append_audit(db, "journey_task", task.id, "task_created", {"kind": task.kind})
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.scalar(
            select(JourneyTask).where(
                JourneyTask.customer_id == customer_id, JourneyTask.dedupe_key == dedupe
            )
        )
    return task


def change_task(db: Session, customer_id: str, identity: str, action: str) -> JourneyTask:
    task = owned(db, JourneyTask, identity, customer_id)
    lock = db.execute(
        update(JourneyTask)
        .where(
            JourneyTask.id == identity,
            or_(JourneyTask.lease_until.is_(None), JourneyTask.lease_until <= utc_now()),
        )
        .values(status=JourneyTask.status)
    )
    if lock.rowcount != 1:
        db.rollback()
        fail("TASK_BUSY", "A check is finishing. Try again in a moment")
    db.refresh(task)
    if task.lease_until and task.lease_until > utc_now():
        fail("TASK_BUSY", "A check is finishing. Try again in a moment")
    if task.status in {"cancelled", "completed", "expired"}:
        fail("TASK_FINISHED", "This task has finished. Create a new task with different conditions")
    if action in {"resume", "check"} and task.expires_at <= utc_now():
        fail("TASK_EXPIRED", "This task has expired")
    if action == "check":
        if task.status in {"paused", "needs_attention"}:
            fail("TASK_PAUSED", "Resume this task before checking")
        task.next_run = utc_now()
    elif action == "resume":
        task.status = "awaiting_review" if task.result.get("cart_id") else "active"
        task.failures = 0
        task.next_run = utc_now() + (
            timedelta(days=task.settings["interval_days"])
            if task.kind == "replenish" and not task.result.get("cart_id")
            else timedelta()
        )
    else:
        task.status = "paused" if action == "pause" else "cancelled"
    append_audit(db, "journey_task", task.id, "task_" + action, {"status": task.status})
    db.commit()
    return task


def _alternatives(db: Session, missing: Product | None, budget: int) -> list[dict]:
    if not missing:
        return []
    products = list(
        db.scalars(
            select(Product)
            .where(
                Product.category == missing.category,
                Product.audience == missing.audience,
                Product.stock > 0,
                Product.price_paise <= budget,
                Product.id != missing.id,
            )
            .order_by(Product.price_paise)
            .limit(3)
        )
    )
    return [product_data(p) for p in products]


def evaluate_task(db: Session, task: JourneyTask):
    now = utc_now()
    if task.expires_at <= now:
        task.status = "expired"
        return
    previous_cart_id = task.result.get("cart_id")
    if previous_cart_id:
        previous = load_cart(db, previous_cart_id)
        order = db.scalar(select(Order).where(Order.cart_id == previous_cart_id))
        if order and order.status == "paid":
            if task.kind == "replenish":
                task.status = "active"
                task.result = {
                    "last_paid_order_id": order.id,
                    "message": "Purchased. The next reminder is scheduled.",
                }
                task.next_run = now + timedelta(days=task.settings["interval_days"])
            else:
                task.status = "completed"
            return
        if (
            not order
            and previous.status == "frozen"
            and previous.expires_at
            and previous.expires_at <= now
        ):
            previous.status = "expired"
            append_audit(db, "cart", previous.id, "cart_expired", {})
        if previous.status not in {"expired", "invalidated"}:
            task.next_run = now + timedelta(minutes=15)
            return
        # Never replace a cart with unresolved payment evidence.
        if order:
            task.result = {
                **task.result,
                "message": "Payment needs reconciliation before recovery.",
            }
            task.next_run = now + timedelta(minutes=15)
            return
        task.result = {}
        task.status = "active"
    settings = task.settings
    budget = settings.get("target_paise") or settings.get("baseline_paise")
    deadline = None
    if task.kind == "watch":
        product = db.get(Product, settings["product_id"])
        if not product or product.stock < 1 or quote_products([product])["total_paise"] > budget:
            task.result = {"message": "Watching for stock and your total-price target."}
            task.next_run = now + timedelta(minutes=15)
            return
        items = [CartItemInput(product_id=product.id, quantity=1)]
    else:
        if task.kind == "replenish":
            order = owned_order(db, task.customer_id, settings["order_id"])
            original = load_cart(db, order.cart_id)
        else:
            original = owned_cart(db, task.customer_id, settings["cart_id"])
            db.execute(update(Cart).where(Cart.id == original.id).values(status=Cart.status))
            db.refresh(original)
            order = db.scalar(select(Order).where(Order.cart_id == original.id))
            if order:
                if order.status == "paid":
                    task.status = "completed"
                    task.result = {"message": "Payment verified; no recovery needed."}
                else:
                    task.result = {
                        "message": "An order already exists. Check verified payment "
                        "status before trying payment again.",
                        "order_id": order.id,
                    }
                    task.next_run = now + timedelta(minutes=15)
                return
            link = db.get(JourneyCart, original.id)
            deadline = link.deadline if link else None
            budget = link.budget_paise if link and link.budget_paise else budget
        unavailable = []
        items = []
        for item in original.items:
            product = db.get(Product, item.product_id)
            if not product or product.stock < item.quantity:
                unavailable.append(
                    {
                        "product_name": item.product_name,
                        "alternatives": _alternatives(db, product, budget),
                    }
                )
            items.append(CartItemInput(product_id=item.product_id, quantity=item.quantity))
        if unavailable or original.compatibility_claims:
            task.result = {
                "message": "Review replacements in a new mission before checkout.",
                "unavailable": unavailable,
                "requires_mission_review": True,
            }
            task.status = "awaiting_review"
            _task_notice(db, task)
            task.next_run = now + timedelta(minutes=15)
            return
    products = [db.get(Product, item.product_id) for item in items]
    quote = quote_products(products, [item.quantity for item in items])
    if quote["total_paise"] > budget or (deadline and quote["estimated_arrival"] > deadline):
        task.result = {
            "message": "Current price or delivery misses your saved limits. "
            "Review a new mission to change them.",
            "quote": quote,
        }
        task.status = "awaiting_review"
        _task_notice(db, task)
        task.next_run = now + timedelta(minutes=15)
        return
    if task.kind == "recovery" and original.status in {"proposed", "frozen", "approved"}:
        original.status = "invalidated"
        original.approved_at = None
        append_audit(db, "cart", original.id, "recovery_approval_revoked", {"task_id": task.id})
    cart = bind_cart(
        db, task.customer_id, items, source=task.kind, budget=budget, deadline=deadline
    )
    task.result = {
        "cart_id": cart.id,
        "quote": quote,
        "message": "A fresh basket is ready. Review the items and confirm delivery.",
    }
    task.status = "awaiting_review"
    task.next_run = now + timedelta(minutes=15)
    append_audit(db, "journey_task", task.id, "review_cart_prepared", {"cart_id": cart.id})
    _task_notice(db, task)


def _task_notice(db: Session, task: JourneyTask):
    key = f"task:{task.id}:{task.result.get('cart_id', 'needs-review')}"
    href = "/journey?cart=" + task.result["cart_id"] if task.result.get("cart_id") else "/journey"
    notify(
        db,
        task.customer_id,
        key,
        {
            "watch": "Your watch needs a look",
            "replenish": "Time to review your next order",
            "recovery": "Checkout recovery update",
        }[task.kind],
        task.result["message"],
        href,
    )


def run_due_tasks(database, only_customer: str | None = None, only_task: str | None = None) -> int:
    now = utc_now()
    with database.session_factory() as db:
        query = (
            select(JourneyTask.id)
            .where(
                JourneyTask.status.in_(["active", "awaiting_review"]),
                JourneyTask.next_run <= now,
                or_(JourneyTask.lease_until.is_(None), JourneyTask.lease_until <= now),
            )
            .order_by(JourneyTask.next_run)
            .limit(50)
        )
        if only_customer:
            query = query.where(JourneyTask.customer_id == only_customer)
        if only_task:
            query = query.where(JourneyTask.id == only_task)
        identities = list(db.scalars(query))
    completed = 0
    for identity in identities:
        lease = str(uuid4())
        with database.session_factory() as db:
            claim = db.execute(
                update(JourneyTask)
                .where(
                    JourneyTask.id == identity,
                    JourneyTask.status.in_(["active", "awaiting_review"]),
                    JourneyTask.next_run <= now,
                    or_(JourneyTask.lease_until.is_(None), JourneyTask.lease_until <= now),
                )
                .values(lease_token=lease, lease_until=now + timedelta(minutes=2))
            )
            db.commit()
            if claim.rowcount != 1:
                continue
        with database.session_factory() as db:
            try:
                # This fenced write holds the row lock through all proposal + notice writes.
                fence = db.execute(
                    update(JourneyTask)
                    .where(
                        JourneyTask.id == identity,
                        JourneyTask.lease_token == lease,
                    )
                    .values(lease_until=utc_now() + timedelta(minutes=2))
                )
                if fence.rowcount != 1:
                    db.rollback()
                    continue
                task = db.get(JourneyTask, identity)
                evaluate_task(db, task)
                task.lease_until = None
                task.lease_token = None
                task.failures = 0
                db.commit()
                completed += 1
            except Exception as error:
                db.rollback()
                task = db.get(JourneyTask, identity)
                if task.lease_token != lease:
                    continue
                task.failures += 1
                task.lease_until = None
                task.lease_token = None
                task.next_run = utc_now() + timedelta(minutes=min(2**task.failures, 60))
                task.result = {
                    "message": "A provider or catalogue check failed. Retrying safely.",
                    "error": type(error).__name__,
                }
                if task.failures >= 5:
                    task.status = "needs_attention"
                    notify(
                        db,
                        task.customer_id,
                        "failed:" + task.id,
                        "A task needs your attention",
                        "Five checks failed. Review the task before resuming.",
                        "/journey",
                    )
                db.commit()
                logger.warning("Journey task %s failed: %s", identity, type(error).__name__)
    return completed
