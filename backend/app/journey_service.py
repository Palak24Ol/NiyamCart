from __future__ import annotations

import itertools
import json
import re
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .agent_service import AgentConfig, run_agent
from .audit import append_audit
from .auth_models import Customer
from .catalog_search import search_products
from .commerce import CommerceError, create_cart, load_cart, utc_now
from .commerce_models import Cart, CartFulfillment, Order
from .commerce_schemas import CartItemInput, CreateCartRequest
from .journey_models import BuyerMemory, JourneyCart, ShoppingMission
from .journey_schemas import MemoryInput, MissionInput
from .models import Product


def fail(code: str, message: str, status: int = 409):
    raise CommerceError(status, code, message)


def owned(db: Session, model, identity: str, customer_id: str):
    record = db.get(model, identity)
    if record is None or record.customer_id != customer_id:
        fail("NOT_FOUND", "This record is not available in your account", 404)
    return record


def memory_data(db: Session, customer: Customer) -> dict:
    row = db.get(BuyerMemory, customer.id)
    data = MemoryInput.model_validate(row.data if row else {}).model_dump()
    return {**data, "name": data["name"] or customer.name, "email": customer.email}


def save_memory(db: Session, customer: Customer, payload: MemoryInput) -> dict:
    row = db.get(BuyerMemory, customer.id)
    if row is None:
        row = BuyerMemory(customer_id=customer.id)
        db.add(row)
    row.data = payload.model_dump()
    db.commit()
    return memory_data(db, customer)


def mission_data(row: ShoppingMission) -> dict:
    return {
        "id": row.id,
        "status": row.status,
        "revision": row.revision,
        "request": row.request,
        "plan": row.plan,
        "messages": row.messages,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def recover_stale_missions(db: Session, customer_id: str):
    stale = list(
        db.scalars(
            select(ShoppingMission).where(
                ShoppingMission.customer_id == customer_id,
                ShoppingMission.status == "planning",
                ShoppingMission.updated_at < utc_now() - timedelta(minutes=2),
            )
        )
    )
    for row in stale:
        changed = db.execute(
            update(ShoppingMission)
            .where(
                ShoppingMission.id == row.id,
                ShoppingMission.revision == row.revision,
                ShoppingMission.status == "planning",
            )
            .values(
                status="draft",
                revision=ShoppingMission.revision + 1,
                updated_at=utc_now(),
                plan={
                    "questions": [
                        "Planning was interrupted. Your goal is saved. "
                        "Select Refresh plan to try again."
                    ],
                    "options": [],
                    "groups": [],
                },
            )
        )
        if changed.rowcount:
            append_audit(db, "mission", row.id, "planning_interrupted", {})
    if stale:
        db.commit()


def save_mission(
    db: Session,
    customer: Customer,
    payload: MissionInput,
    identity: str | None = None,
    expected: int | None = None,
) -> ShoppingMission:
    data = payload.model_dump(mode="json", exclude={"expected_revision"})
    if identity:
        row = owned(db, ShoppingMission, identity, customer.id)
        if row.status == "planning":
            fail("MISSION_BUSY", "A plan is being prepared. Please wait for it to finish")
        changed = db.execute(
            update(ShoppingMission)
            .where(
                ShoppingMission.id == row.id,
                ShoppingMission.revision == expected,
                ShoppingMission.status != "planning",
            )
            .values(revision=ShoppingMission.revision + 1, updated_at=utc_now())
        )
        if changed.rowcount != 1:
            db.rollback()
            fail("STALE_MISSION", "This mission changed in another tab. Refresh and try again")
        db.refresh(row)
    else:
        if (
            len(
                list(
                    db.scalars(
                        select(ShoppingMission.id).where(ShoppingMission.customer_id == customer.id)
                    )
                )
            )
            >= 100
        ):
            fail("MISSION_LIMIT", "Your account has reached the 100-mission limit")
        row = ShoppingMission(id=str(uuid4()), customer_id=customer.id, revision=0, messages=[])
        db.add(row)
    row.request = data
    row.status = "draft"
    row.plan = {}
    row.messages = [*row.messages[-19:], {"role": "buyer", "text": data["message"]}]
    row.updated_at = utc_now()
    db.flush()
    append_audit(db, "mission", row.id, "mission_saved", {"revision": row.revision})
    db.commit()
    return row


def product_data(product: Product) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "price_paise": product.price_paise,
        "stock": product.stock,
        "image": product.image,
        "delivery_days": product.delivery_days,
        "free_delivery": product.free_delivery,
        "return_window_days": product.return_window_days,
    }


def quote_products(products: list[Product], quantities: list[int] | None = None) -> dict:
    quantities = quantities or [1] * len(products)
    subtotal = sum(
        p.price_paise * quantity for p, quantity in zip(products, quantities, strict=True)
    )
    shipping = 0 if all(p.free_delivery for p in products) else 4900
    days = max(p.delivery_days for p in products) + 2
    return {
        "subtotal_paise": subtotal,
        "shipping_paise": shipping,
        "total_paise": subtotal + shipping,
        "eta_max_days": days,
        "estimated_arrival": (datetime.now(UTC).date() + timedelta(days=days)).isoformat(),
        "delivery_source": "catalogue_estimate",
        "delivery_guaranteed": False,
    }


def validate_quote(quote: dict, budget: int | None, deadline: str | None):
    if budget is not None and quote["total_paise"] > budget:
        fail("BUDGET_EXCEEDED", "The total including delivery exceeds your budget")
    if deadline and quote["estimated_arrival"] > deadline:
        fail("DEADLINE_UNAVAILABLE", "The catalogue delivery estimate misses your deadline")


def matches_mission_item(product: Product, requirement: str) -> bool:
    # A "T-shirt bra" is underwear, not a shirt: broad catalogue keyword matches
    # must not silently substitute a different item type in a complete basket.
    words = set(re.findall(r"[a-z]+", requirement.casefold()))
    if words & {"shirt", "shirts"} and not words & {"bra", "bras"}:
        name = set(re.findall(r"[a-z]+", product.name.casefold()))
        return bool(name & {"shirt", "shirts"}) and not name & {"bra", "bras"}
    return True


def plan_mission(db: Session, customer: Customer, identity: str, expected: int) -> ShoppingMission:
    row = owned(db, ShoppingMission, identity, customer.id)
    recover_stale_missions(db, customer.id)
    db.refresh(row)
    locked = db.execute(
        update(ShoppingMission)
        .where(
            ShoppingMission.id == identity,
            ShoppingMission.revision == expected,
            ShoppingMission.status != "planning",
        )
        .values(status="planning", revision=ShoppingMission.revision + 1, updated_at=utc_now())
    )
    if locked.rowcount != 1:
        db.rollback()
        fail("STALE_MISSION", "The mission is busy or changed. Refresh and try again")
    db.commit()
    db.refresh(row)
    planning_revision = row.revision
    try:
        request = row.request
        memory = memory_data(db, customer)
        allowed_memory = request.get("use_memory") and memory["use_for_agent"]
        budget = request.get("budget_paise")
        if budget is None and allowed_memory:
            budget = memory["budget_paise"]
        requirements = request.get("requirements", [])
        questions = []
        if not budget:
            questions.append("What is your total budget, including delivery?")
        if not requirements:
            questions.append("Which items should I find? Add one short item description per line.")
        if questions:
            row.status = "needs_details"
            row.plan = {"questions": questions, "groups": [], "options": []}
        else:
            context = {
                "goal": request["message"],
                "requirements": requirements,
                "budget_paise": budget,
                "deadline": request.get("deadline"),
            }
            if allowed_memory:
                context["buyer_preferences"] = {
                    key: memory[key] for key in ("size", "brands", "rejected_product_ids")
                }
            # One bounded model run per explicit plan request. Background checks use facts only.
            result = run_agent(
                db,
                "Compare products for this saved shopping mission. "
                "Search and explain options for human review. Buyer data: "
                + json.dumps(context, ensure_ascii=False)[:1750],
                config=replace(AgentConfig.from_env(), max_steps=3, request_timeout_seconds=8.0),
            )
            # A previous process/request must not overwrite a recovered or edited mission.
            db.refresh(row)
            if row.revision != planning_revision or row.status != "planning":
                fail("STALE_MISSION", "Planning was superseded. Refresh to see the latest result")
            catalog = list(db.scalars(select(Product)))
            preferred = set(result.recommended_product_ids)
            rejected = set(memory["rejected_product_ids"]) if allowed_memory else set()
            brands = {b.casefold() for b in memory["brands"]} if allowed_memory else set()
            groups = []
            for requirement in requirements:
                candidates = [
                    match.product
                    for match in search_products(catalog, requirement, max_price_paise=budget)
                    if match.product.id not in rejected
                    and matches_mission_item(match.product, requirement)
                ]
                candidates = [
                    p
                    for p in candidates
                    if not request.get("deadline")
                    or quote_products([p])["estimated_arrival"] <= request["deadline"]
                ]
                candidates.sort(
                    key=lambda p: (
                        p.brand.casefold() not in brands if brands else False,
                        p.id not in preferred,
                        p.price_paise,
                        p.id,
                    )
                )
                groups.append(
                    {
                        "requirement": requirement,
                        "products": [product_data(p) for p in candidates[:8]],
                    }
                )
            by_id = {p.id: p for p in catalog}
            options = []
            if all(group["products"] for group in groups):
                for combination in itertools.product(*(g["products"] for g in groups)):
                    ids = [p["id"] for p in combination]
                    if len(ids) != len(set(ids)):
                        continue
                    quote = quote_products([by_id[pid] for pid in ids])
                    if quote["total_paise"] <= budget:
                        options.append({"product_ids": ids, **quote})
            options.sort(key=lambda option: (option["total_paise"], option["product_ids"]))
            row.status = "ready" if options else "needs_details"
            row.plan = {
                "groups": groups,
                "options": options[:3],
                "budget_paise": budget,
                "agent_session_id": result.session_id,
                "agent_status": result.status,
                "agent_answer": result.answer,
                "generated_at": utc_now().isoformat(),
                "questions": []
                if options
                else [
                    "No complete basket meets every item, budget and delivery constraint. "
                    "Adjust the item descriptions, budget or deadline and plan again."
                ],
                "memory_used": bool(allowed_memory),
                "size_note": "Size preferences are advisory; this catalogue has no "
                "size-specific stock. Confirm variants with the merchant.",
            }
        row.messages = [
            *row.messages[-19:],
            {
                "role": "assistant",
                "text": " ".join(row.plan.get("questions", []))
                or "Your basket options are ready for review.",
            },
        ]
        row.updated_at = utc_now()
        append_audit(
            db,
            "mission",
            row.id,
            "mission_planned",
            {
                "status": row.status,
                "options": len(row.plan.get("options", [])),
                "agent_session_id": row.plan.get("agent_session_id"),
                "revision": row.revision,
            },
        )
        db.commit()
        return row
    except Exception:
        db.rollback()
        db.refresh(row)
        if row.revision == planning_revision and row.status == "planning":
            row.status = "draft"
            row.plan = {
                "questions": [
                    "Planning could not finish. Your goal is saved. Select Refresh plan to retry."
                ],
                "options": [],
                "groups": [],
            }
            row.updated_at = utc_now()
            db.commit()
        raise


def bind_cart(
    db: Session,
    customer_id: str,
    items: list[CartItemInput],
    *,
    source: str,
    budget: int | None = None,
    deadline: str | None = None,
    mission_id: str | None = None,
) -> Cart:
    products = [db.get(Product, item.product_id) for item in items]
    if any(p is None for p in products):
        fail("PRODUCT_UNAVAILABLE", "A product is no longer available")
    quote = quote_products(products, [item.quantity for item in items])
    validate_quote(quote, budget, deadline)
    cart = create_cart(db, CreateCartRequest(items=items), commit=False)
    db.add(
        JourneyCart(
            cart_id=cart.id,
            customer_id=customer_id,
            mission_id=mission_id,
            source=source,
            budget_paise=budget,
            deadline=deadline,
        )
    )
    db.flush()
    return cart


def select_plan(
    db: Session, customer: Customer, identity: str, expected: int, product_ids: list[str]
) -> Cart:
    row = owned(db, ShoppingMission, identity, customer.id)
    if row.revision != expected or row.status not in {"ready", "checkout"}:
        fail("STALE_MISSION", "Refresh this mission and prepare a current plan")
    if product_ids not in [option["product_ids"] for option in row.plan.get("options", [])]:
        fail("INVALID_OPTION", "Choose one of the complete proposed baskets")
    previous = row.plan.get("cart_id")
    if previous and row.plan.get("selected_product_ids") == product_ids:
        cart = load_cart(db, previous)
        if cart.status in {"proposed", "frozen", "approved", "ordered"}:
            return cart
    # Serialize selection before creating a commerce proposal.
    claim = db.execute(
        update(ShoppingMission)
        .where(
            ShoppingMission.id == identity,
            ShoppingMission.revision == expected,
            ShoppingMission.status.in_(["ready", "checkout"]),
        )
        .values(status="selecting")
    )
    if claim.rowcount != 1:
        db.rollback()
        fail("MISSION_BUSY", "A basket is already being selected")
    # Re-read after obtaining the write lock: another tab may just have selected this option.
    db.refresh(row)
    prior_id = row.plan.get("cart_id")
    if prior_id and row.plan.get("selected_product_ids") == product_ids:
        prior_cart = load_cart(db, prior_id)
        if prior_cart.status in {"proposed", "frozen", "approved", "ordered"}:
            row.status = "checkout"
            db.commit()
            return prior_cart
    try:
        cart = bind_cart(
            db,
            customer.id,
            [CartItemInput(product_id=p, quantity=1) for p in product_ids],
            source="mission",
            mission_id=row.id,
            budget=row.plan["budget_paise"],
            deadline=row.request.get("deadline"),
        )
        row.status = "checkout"
        row.plan = {**row.plan, "cart_id": cart.id, "selected_product_ids": product_ids}
        append_audit(db, "mission", row.id, "basket_selected", {"cart_id": cart.id})
        db.commit()
        return cart
    except Exception:
        db.rollback()
        db.refresh(row)
        row.status = "ready"
        db.commit()
        raise


def owned_cart(db: Session, customer_id: str, cart_id: str) -> Cart:
    cart = load_cart(db, cart_id)
    link = db.get(JourneyCart, cart_id)
    owner = (
        link.customer_id if link else (cart.fulfillment.customer_id if cart.fulfillment else None)
    )
    if owner != customer_id:
        fail("NOT_FOUND", "This cart is not available in your account", 404)
    return cart


def owned_orders(db: Session, customer_id: str) -> list[Order]:
    ids = select(JourneyCart.cart_id).where(JourneyCart.customer_id == customer_id)
    delivered = select(CartFulfillment.cart_id).where(CartFulfillment.customer_id == customer_id)
    return list(
        db.scalars(
            select(Order)
            .where(Order.cart_id.in_(ids) | Order.cart_id.in_(delivered))
            .order_by(Order.created_at.desc())
        )
    )


def owned_order(db: Session, customer_id: str, identity: str) -> Order:
    order = db.get(Order, identity)
    if order is None:
        fail("NOT_FOUND", "Order not found", 404)
    owned_cart(db, customer_id, order.cart_id)
    return order


def enforce_journey_constraints(db: Session, cart: Cart):
    link = db.get(JourneyCart, cart.id)
    if link is None:
        return
    products = [db.get(Product, item.product_id) for item in cart.items]
    if any(p is None for p in products):
        fail("PRODUCT_UNAVAILABLE", "A mission product is unavailable")
    quote = quote_products(products, [item.quantity for item in cart.items])
    validate_quote(quote, link.budget_paise, link.deadline)
    if cart.fulfillment is None:
        fail("DELIVERY_REQUIRED", "Confirm a delivery address before locking this basket")
    if link.budget_paise is not None and cart.total_paise > link.budget_paise:
        fail("BUDGET_EXCEEDED", "The final total exceeds your mission budget")


def parse_day(value: str) -> date:
    return date.fromisoformat(value)
