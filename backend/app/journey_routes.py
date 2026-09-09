import hashlib
import json
import os
import secrets
from datetime import timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from .audit import verify_audit
from .auth_models import Customer
from .auth_service import SESSION_COOKIE, load_customer_from_token
from .commerce import utc_now
from .commerce_models import Cart, Order
from .commerce_schemas import CartItemInput, CartResponse
from .journey_aftercare import (
    case_data,
    confirm_case,
    order_data,
    payment_receipt,
    prepare_case,
    record_shipment,
    verify_shipment_signature,
)
from .journey_agent import aftercare_agent
from .journey_models import (
    BuyerAccessKey,
    BuyerMemory,
    ExternalBuyerQuote,
    JourneyCart,
    JourneyNotice,
    JourneyTask,
    ShoppingMission,
    SupportCase,
)
from .journey_payments import reconcile_order, resume_order
from .journey_schemas import (
    ExternalQuoteInput,
    MemoryInput,
    MissionInput,
    MissionRevision,
    OrderQuestion,
    PlanInput,
    SelectPlanInput,
    ShipmentInput,
    SupportInput,
    TaskAction,
    TaskInput,
)
from .journey_service import (
    bind_cart,
    fail,
    memory_data,
    mission_data,
    owned,
    owned_cart,
    owned_order,
    owned_orders,
    plan_mission,
    quote_products,
    recover_stale_missions,
    save_memory,
    save_mission,
    select_plan,
)
from .journey_tasks import change_task, create_task, run_due_tasks, task_data
from .models import Product


def install_journey_routes(app: FastAPI):
    def session():
        yield from app.state.db.session()

    DB = Annotated[Session, Depends(session)]

    def customer(request: Request, db: DB):
        return load_customer_from_token(db, request.cookies.get(SESSION_COOKIE))

    Buyer = Annotated[Customer, Depends(customer)]

    @app.get("/api/journey", tags=["buyer journey"])
    def dashboard(db: DB, buyer: Buyer):
        recover_stale_missions(db, buyer.id)
        return {
            "missions": [
                mission_data(m)
                for m in db.scalars(
                    select(ShoppingMission)
                    .where(ShoppingMission.customer_id == buyer.id)
                    .order_by(ShoppingMission.updated_at.desc())
                )
            ],
            "tasks": [
                task_data(t)
                for t in db.scalars(
                    select(JourneyTask)
                    .where(JourneyTask.customer_id == buyer.id)
                    .order_by(JourneyTask.created_at.desc())
                )
            ],
            "notices": [
                {
                    "id": n.id,
                    "title": n.title,
                    "body": n.body,
                    "href": n.href,
                    "read_at": n.read_at,
                    "created_at": n.created_at,
                }
                for n in db.scalars(
                    select(JourneyNotice)
                    .where(JourneyNotice.customer_id == buyer.id)
                    .order_by(JourneyNotice.created_at.desc())
                    .limit(100)
                )
            ],
            "memory": memory_data(db, buyer),
            "scheduler": {
                "enabled": os.getenv("JOURNEY_WORKER_ENABLED", "true").lower() == "true",
                "interval_seconds": 60,
                "channel": "in_app",
                "requires_running_backend": True,
            },
            "fulfillment_connected": len(os.getenv("MERCHANT_FULFILLMENT_WEBHOOK_SECRET", ""))
            >= 32,
            "demo_fulfillment_enabled": os.getenv("JOURNEY_DEMO_FULFILLMENT", "false") == "true",
        }

    @app.get("/api/journey/carts", tags=["buyer journey"])
    def saved_baskets(db: DB, buyer: Buyer):
        records = db.execute(
            select(JourneyCart, Cart, Order.id)
            .join(Cart, Cart.id == JourneyCart.cart_id)
            .outerjoin(Order, Order.cart_id == Cart.id)
            .where(
                JourneyCart.customer_id == buyer.id,
                Cart.status.notin_(["invalidated", "expired"]),
                or_(Order.id.is_(None), Order.status != "paid"),
            )
            .order_by(JourneyCart.created_at.desc())
            .limit(20)
        ).all()
        return {
            "items": [
                {
                    "cart_id": cart.id,
                    "source": link.source,
                    "total_paise": cart.total_paise,
                    "order_id": order_id,
                    "items": [
                        {"name": item.product_name, "quantity": item.quantity}
                        for item in cart.items
                    ],
                }
                for link, cart, order_id in records
            ]
        }

    @app.get("/api/customer/memory", tags=["buyer journey"])
    def get_memory(db: DB, buyer: Buyer):
        return memory_data(db, buyer)

    @app.put("/api/customer/memory", tags=["buyer journey"])
    def put_memory(payload: MemoryInput, db: DB, buyer: Buyer):
        return save_memory(db, buyer, payload)

    @app.post("/api/customer/memory/forget", tags=["buyer journey"])
    def forget_memory(db: DB, buyer: Buyer):
        row = db.get(BuyerMemory, buyer.id)
        if row:
            db.delete(row)
            db.commit()
        return {
            "status": "forgotten",
            "message": "Saved preferences cleared. Existing missions "
            "and their audit records are retained.",
        }

    @app.post("/api/journey/missions", tags=["buyer journey"], status_code=201)
    def new_mission(payload: MissionInput, db: DB, buyer: Buyer):
        return mission_data(save_mission(db, buyer, payload))

    @app.put("/api/journey/missions/{identity}", tags=["buyer journey"])
    def revise_mission(identity: str, payload: MissionRevision, db: DB, buyer: Buyer):
        return mission_data(save_mission(db, buyer, payload, identity, payload.expected_revision))

    @app.post("/api/journey/missions/{identity}/plan", tags=["buyer journey"])
    def plan(identity: str, payload: PlanInput, db: DB, buyer: Buyer):
        return mission_data(plan_mission(db, buyer, identity, payload.expected_revision))

    @app.post("/api/journey/missions/{identity}/select", tags=["buyer journey"])
    def choose(identity: str, payload: SelectPlanInput, db: DB, buyer: Buyer):
        cart = select_plan(db, buyer, identity, payload.expected_revision, payload.product_ids)
        return {"cart_id": cart.id, "review_url": "/journey?cart=" + cart.id}

    @app.get("/api/journey/missions/{identity}/audit", tags=["buyer journey"])
    def mission_audit(identity: str, db: DB, buyer: Buyer):
        owned(db, ShoppingMission, identity, buyer.id)
        return verify_audit(db, "mission", identity)

    @app.get("/api/journey/carts/{identity}", tags=["buyer journey"])
    def review_cart(identity: str, db: DB, buyer: Buyer):
        cart = owned_cart(db, buyer.id, identity)
        return {
            "cart": CartResponse.model_validate(cart),
            "address_id": cart.fulfillment.address_id if cart.fulfillment else None,
            "order_id": cart.order.id if cart.order else None,
            "quote": quote_products(
                [db.get(Product, i.product_id) for i in cart.items],
                [i.quantity for i in cart.items],
            ),
        }

    @app.post("/api/journey/tasks", tags=["buyer journey"], status_code=201)
    def new_task(payload: TaskInput, db: DB, buyer: Buyer):
        task = create_task(db, buyer.id, payload)
        run_due_tasks(app.state.db, buyer.id, task.id)
        db.expire_all()
        return task_data(task)

    @app.post("/api/journey/tasks/{identity}/action", tags=["buyer journey"])
    def task_action(identity: str, payload: TaskAction, db: DB, buyer: Buyer):
        task = change_task(db, buyer.id, identity, payload.action)
        if payload.action == "check":
            run_due_tasks(app.state.db, buyer.id, identity)
            db.expire_all()
        return task_data(task)

    @app.post("/api/journey/notices/{identity}/read", tags=["buyer journey"])
    def read_notice(identity: str, db: DB, buyer: Buyer):
        notice = owned(db, JourneyNotice, identity, buyer.id)
        notice.read_at = utc_now()
        db.commit()
        return {"status": "read"}

    @app.get("/api/customer/orders", tags=["buyer journey"])
    def customer_orders(db: DB, buyer: Buyer):
        return {"items": [order_data(db, order) for order in owned_orders(db, buyer.id)]}

    @app.get("/api/customer/orders/{identity}/receipt", tags=["buyer journey"])
    def receipt(identity: str, db: DB, buyer: Buyer):
        return PlainTextResponse(
            payment_receipt(db, buyer.id, identity),
            headers={"Content-Disposition": 'attachment; filename="niyamcart-test-receipt.txt"'},
        )

    @app.post("/api/customer/orders/{identity}/reconcile", tags=["buyer journey"])
    def reconcile(identity: str, db: DB, buyer: Buyer):
        return reconcile_order(db, buyer.id, identity, app.state.razorpay_gateway)

    @app.post("/api/customer/orders/{identity}/resume", tags=["buyer journey"])
    def resume(identity: str, db: DB, buyer: Buyer):
        return resume_order(db, buyer.id, identity, app.state.razorpay_gateway)

    @app.post("/api/customer/orders/{identity}/ask", tags=["buyer journey"])
    def order_question(identity: str, payload: OrderQuestion, db: DB, buyer: Buyer):
        return aftercare_agent(db, buyer.id, identity, payload.message)

    @app.get("/api/customer/orders/{identity}/replacements", tags=["buyer journey"])
    def replacements(identity: str, product_id: str, db: DB, buyer: Buyer):
        order = owned_order(db, buyer.id, identity)
        if product_id not in [i.product_id for i in order.cart.items]:
            fail("NOT_FOUND", "This product is not part of your order", 404)
        product = db.get(Product, product_id)
        from .journey_service import product_data

        return {
            "items": [
                product_data(p)
                for p in db.scalars(
                    select(Product)
                    .where(
                        Product.category == product.category,
                        Product.stock > 0,
                        Product.id != product_id,
                    )
                    .order_by(Product.price_paise)
                    .limit(12)
                )
            ]
        }

    @app.post("/api/customer/orders/{identity}/cases", tags=["buyer journey"])
    def new_case(identity: str, payload: SupportInput, db: DB, buyer: Buyer):
        return case_data(prepare_case(db, buyer.id, identity, payload))

    @app.post("/api/journey/cases/{identity}/confirm", tags=["buyer journey"])
    def submit_case(identity: str, db: DB, buyer: Buyer):
        return case_data(confirm_case(db, buyer.id, identity))

    @app.post("/api/journey/cases/{identity}/cancel", tags=["buyer journey"])
    def cancel_case(identity: str, db: DB, buyer: Buyer):
        case = owned(db, SupportCase, identity, buyer.id)
        if case.status != "draft":
            fail("CASE_SUBMITTED", "Contact the merchant to withdraw a submitted case")
        case.status = "cancelled"
        db.commit()
        return case_data(case)

    @app.post("/api/journey/demo/shipment", tags=["buyer journey demo"])
    def demo_shipment(payload: ShipmentInput, db: DB, buyer: Buyer):
        if os.getenv("JOURNEY_DEMO_FULFILLMENT", "false") != "true":
            fail("DEMO_DISABLED", "Shipment simulation is disabled", 403)
        owned_order(db, buyer.id, payload.order_id)
        event = record_shipment(db, payload, "demo_simulation")
        return {"status": event.status, "source": event.source}

    @app.post("/api/fulfillment/merchant-webhook", tags=["merchant integration"])
    async def shipment_webhook(
        request: Request,
        db: DB,
        x_merchant_timestamp: str = Header(default=""),
        x_merchant_signature: str = Header(default=""),
    ):
        body = await request.body()
        if len(body) > 16_384:
            fail("PAYLOAD_TOO_LARGE", "Shipment event is too large", 413)
        verify_shipment_signature(body, x_merchant_timestamp, x_merchant_signature)
        try:
            payload = ShipmentInput.model_validate_json(body)
        except ValidationError:
            fail("INVALID_EVENT", "Invalid shipment event fields", 422)
        event = record_shipment(db, payload, "merchant_webhook")
        return {"event_id": event.id, "status": event.status}

    @app.get("/.well-known/buyer-commerce.json", tags=["external buyer"])
    def buyer_contract():
        return {
            "name": "NiyamCart bounded buyer API",
            "version": "1.0",
            "protocol": "niyamcart-custom-demo",
            "currency": "INR",
            "money_unit": "paise",
            "catalog": "/.well-known/agent-catalog.json",
            "policy": "/.well-known/agent-policy.json",
            "quote": "/api/buyer/quotes",
            "authentication": "short-lived bearer key",
            "authority": "quote_and_review_only",
            "payments": "human_approved_test_checkout",
            "limits": {"products_per_quote": 4, "quotes_per_key": 20, "key_ttl_minutes": 15},
            "standards_claim": "This is not ACP, AP2, UAP or x402 certification.",
        }

    @app.post("/api/journey/buyer-key", tags=["external buyer"])
    def buyer_key(db: DB, buyer: Buyer):
        # One current key per account. Rotating immediately revokes earlier keys.
        db.execute(
            update(BuyerAccessKey)
            .where(BuyerAccessKey.customer_id == buyer.id)
            .values(expires_at=utc_now())
        )
        raw = secrets.token_urlsafe(32)
        expiry = utc_now() + timedelta(minutes=15)
        db.add(
            BuyerAccessKey(
                digest=hashlib.sha256(raw.encode()).hexdigest(),
                customer_id=buyer.id,
                expires_at=expiry,
            )
        )
        db.commit()
        return {"key": raw, "expires_at": expiry, "scope": "quotes_only"}

    @app.post("/api/journey/buyer-key/revoke", tags=["external buyer"])
    def revoke_key(db: DB, buyer: Buyer):
        db.execute(
            update(BuyerAccessKey)
            .where(BuyerAccessKey.customer_id == buyer.id)
            .values(expires_at=utc_now())
        )
        db.commit()
        return {"status": "revoked"}

    @app.post("/api/buyer/quotes", tags=["external buyer"])
    def external_quote(
        payload: ExternalQuoteInput, db: DB, authorization: str = Header(default="")
    ):
        if not authorization.startswith("Bearer "):
            fail("BUYER_AUTH_REQUIRED", "Use a buyer quote key", 401)
        digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
        key = db.get(BuyerAccessKey, digest)
        if not key or key.expires_at <= utc_now():
            fail("BUYER_KEY_EXPIRED", "Buyer quote key is invalid or expired", 401)
        key_lock = db.execute(
            update(BuyerAccessKey)
            .where(BuyerAccessKey.digest == digest, BuyerAccessKey.expires_at > utc_now())
            .values(expires_at=BuyerAccessKey.expires_at)
        )
        if key_lock.rowcount != 1:
            db.rollback()
            fail("BUYER_KEY_EXPIRED", "Buyer quote key was revoked or expired", 401)
        fingerprint = hashlib.sha256(
            json.dumps(payload.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        previous = db.scalar(
            select(ExternalBuyerQuote).where(
                ExternalBuyerQuote.customer_id == key.customer_id,
                ExternalBuyerQuote.request_key == payload.request_key,
            )
        )
        if previous:
            if previous.request_hash != fingerprint:
                fail("QUOTE_KEY_REUSED", "Request key was used for different quote inputs")
            if previous.expires_at <= utc_now():
                fail("QUOTE_EXPIRED", "Request a fresh quote with a new request key")
            return previous.quote
        if (
            len(
                list(
                    db.scalars(
                        select(ExternalBuyerQuote.id).where(
                            ExternalBuyerQuote.access_digest == digest
                        )
                    )
                )
            )
            >= 20
        ):
            fail("QUOTE_LIMIT", "This buyer key has reached its 20-quote limit", 429)
        if len(payload.product_ids) != len(set(payload.product_ids)):
            fail("DUPLICATE_PRODUCT", "Each product must appear once", 422)
        cart = bind_cart(
            db,
            key.customer_id,
            [CartItemInput(product_id=p, quantity=1) for p in payload.product_ids],
            source="external_buyer",
            budget=payload.budget_paise,
            deadline=payload.deadline.isoformat() if payload.deadline else None,
        )
        quote = quote_products([db.get(Product, p) for p in payload.product_ids])
        expiry = utc_now() + timedelta(minutes=15)
        response = {
            **quote,
            "cart_id": cart.id,
            "quote_id": str(uuid4()),
            "expires_at": expiry.isoformat(),
            "approval_required": True,
            "review_url": "/journey?cart=" + cart.id,
            "test_mode": True,
        }
        db.add(
            ExternalBuyerQuote(
                id=response["quote_id"],
                customer_id=key.customer_id,
                access_digest=digest,
                request_key=payload.request_key,
                request_hash=fingerprint,
                cart_id=cart.id,
                quote=response,
                expires_at=expiry,
            )
        )
        db.commit()
        return response
