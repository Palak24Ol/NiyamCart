import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.agent_service import FunctionCall, ProviderTurn
from app.commerce import utc_now
from app.commerce_models import Cart, Order
from app.journey_agent import aftercare_agent
from app.journey_models import JourneyNotice, JourneyTask, ShoppingMission
from app.journey_tasks import run_due_tasks
from app.journey_worker import observe_orders
from app.main import create_app
from app.models import Product
from app.razorpay_service import RazorpayError
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_advanced_checkout import address
from test_razorpay import FakeRazorpayGateway


class RecoveryGateway(FakeRazorpayGateway):
    def fetch_order_payments(self, order_id):
        items = [p for p in self.payments.values() if p["order_id"] == order_id]
        return {"count": len(items), "items": items}


def signup(client, email="journey@example.com"):
    response = client.post(
        "/api/auth/signup",
        json={"name": "Journey Tester", "email": email, "password": "SafePass123"},
    )
    assert response.status_code == 201
    return response.json()["user"]["id"]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("JOURNEY_WORKER_ENABLED", "false")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "app.journey_service.run_agent",
        lambda *args, **kwargs: SimpleNamespace(
            session_id="offline-journey",
            recommended_product_ids=[],
            status="degraded",
            answer="Catalogue fallback",
        ),
    )
    gateway = RecoveryGateway()
    app = create_app(f"sqlite:///{tmp_path / 'journey.db'}", razorpay_gateway=gateway)
    with TestClient(app) as client:
        buyer = signup(client)
        yield app, client, gateway, buyer


def mission(client, budget=500_000, deadline=None):
    product = client.get("/api/products/P-001").json()
    response = client.post(
        "/api/journey/missions",
        json={
            "title": "Office purchase",
            "message": "Find this item for work",
            "requirements": [product["name"]],
            "budget_paise": budget,
            "deadline": deadline,
        },
    )
    assert response.status_code == 201, response.text
    saved = response.json()
    planned = client.post(
        f"/api/journey/missions/{saved['id']}/plan", json={"expected_revision": saved["revision"]}
    )
    assert planned.status_code == 200, planned.text
    return planned.json()


def selected_cart(client):
    planned = mission(client)
    response = client.post(
        f"/api/journey/missions/{planned['id']}/select",
        json={
            "expected_revision": planned["revision"],
            "product_ids": planned["plan"]["options"][0]["product_ids"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["cart_id"]


def checkout(client, gateway, paid=True):
    cart_id = selected_cart(client)
    saved = address(client)
    assert (
        client.post(
            f"/api/carts/{cart_id}/delivery", json={"address_id": saved["id"], "confirmed": True}
        ).status_code
        == 200
    )
    client.post(
        f"/api/carts/{cart_id}/payment-offer", json={"offer_key": "standard", "confirmed": True}
    )
    response = client.post(f"/api/carts/{cart_id}/finalize")
    assert response.status_code == 200, response.text
    frozen = response.json()
    assert (
        client.post(
            f"/api/carts/{cart_id}/approve", json={"cart_hash": frozen["cart_hash"]}
        ).status_code
        == 200
    )
    order = client.post(
        "/api/orders",
        json={
            "cart_id": cart_id,
            "cart_hash": frozen["cart_hash"],
            "idempotency_key": "journey-" + cart_id,
        },
    ).json()
    provider = client.post(f"/api/orders/{order['id']}/razorpay-checkout").json()
    if paid:
        gateway.payments["pay_JourneyTest"] = {
            "id": "pay_JourneyTest",
            "order_id": provider["razorpay_order_id"],
            "amount": order["total_paise"],
            "currency": "INR",
            "status": "captured",
            "captured": True,
        }
        response = client.post(
            "/api/payments/razorpay/verify",
            json={
                "internal_order_id": order["id"],
                "razorpay_order_id": provider["razorpay_order_id"],
                "razorpay_payment_id": "pay_JourneyTest",
                "razorpay_signature": gateway.checkout_signature(
                    provider["razorpay_order_id"], "pay_JourneyTest"
                ),
            },
        )
        assert response.status_code == 200, response.text
    return order, cart_id


def test_memory_is_server_backed_opt_in_and_account_scoped(setup):
    _, client, _, _ = setup
    assert client.get("/api/customer/memory").json()["use_for_agent"] is False
    assert (
        client.put(
            "/api/customer/memory",
            json={"size": "M", "brands": ["Demo"], "use_for_agent": True, "budget_paise": 200_000},
        ).status_code
        == 200
    )
    client.post("/api/auth/logout")
    assert client.get("/api/customer/memory").status_code == 401
    signup(client, "second@example.com")
    assert client.get("/api/customer/memory").json()["size"] == ""
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": "journey@example.com", "password": "SafePass123"})
    assert client.get("/api/customer/memory").json()["size"] == "M"
    assert client.post("/api/customer/memory/forget").status_code == 200
    assert client.get("/api/customer/memory").json()["use_for_agent"] is False


def test_mission_clarifies_missing_details_and_rejects_stale_revision(setup):
    _, client, _, _ = setup
    row = client.post(
        "/api/journey/missions", json={"title": "Wedding", "message": "Help me shop"}
    ).json()
    result = client.post(
        f"/api/journey/missions/{row['id']}/plan", json={"expected_revision": 0}
    ).json()
    assert result["status"] == "needs_details"
    assert len(result["plan"]["questions"]) == 2
    assert (
        client.post(
            f"/api/journey/missions/{row['id']}/plan", json={"expected_revision": 0}
        ).status_code
        == 409
    )


def test_plan_enforces_budget_delivery_and_selected_products(setup):
    _, client, _, _ = setup
    assert not mission(client, budget=100)["plan"]["options"]
    assert not mission(client, deadline=utc_now().date().isoformat())["plan"]["options"]
    row = mission(client)
    assert row["status"] == "ready"
    assert row["plan"]["options"][0]["total_paise"] <= 500_000
    forged = client.post(
        f"/api/journey/missions/{row['id']}/select",
        json={"expected_revision": row["revision"], "product_ids": ["P-002"]},
    )
    assert forged.status_code == 409
    assert client.get(f"/api/journey/missions/{row['id']}/audit").json()["valid"]


def test_shirt_mission_does_not_substitute_tshirt_bra(setup):
    _, client, _, _ = setup
    row = client.post(
        "/api/journey/missions",
        json={
            "title": "Office shirt",
            "message": "Find a blue shirt",
            "requirements": ["blue shirt"],
            "budget_paise": 200_000,
        },
    ).json()
    plan = client.post(
        f"/api/journey/missions/{row['id']}/plan", json={"expected_revision": row["revision"]}
    ).json()["plan"]
    assert plan["options"]
    assert all("bra" not in p["name"].lower() for p in plan["groups"][0]["products"])


def test_provider_timeout_returns_catalogue_options(setup, monkeypatch):
    from app.agent_service import run_agent

    _, client, _, _ = setup

    class TimeoutProvider:
        def respond(self, _):
            raise TimeoutError("fixture provider timeout")

    monkeypatch.setattr("app.journey_service.run_agent", run_agent)
    monkeypatch.setattr("app.agent_service.default_provider", lambda config: TimeoutProvider())
    result = mission(client)
    assert result["status"] == "ready"
    assert result["plan"]["agent_status"] == "degraded"
    assert result["plan"]["options"]


def test_interrupted_mission_becomes_retryable(setup):
    app, client, _, _ = setup
    row = mission(client)
    with app.state.db.session_factory() as db:
        stored = db.get(ShoppingMission, row["id"])
        stored.status = "planning"
        stored.updated_at = utc_now() - timedelta(minutes=3)
        db.commit()
    recovered = client.get("/api/journey").json()["missions"][0]
    assert recovered["status"] == "draft"
    assert recovered["revision"] > row["revision"]
    assert "interrupted" in recovered["plan"]["questions"][0]
    assert (
        client.post(
            f"/api/journey/missions/{row['id']}/plan",
            json={"expected_revision": recovered["revision"]},
        ).json()["status"]
        == "ready"
    )


def test_saved_baskets_visible_only_to_owner_and_paid_baskets_removed(setup):
    _, client, gateway, _ = setup
    first = selected_cart(client)
    assert client.get("/api/journey/carts").json()["items"][0]["cart_id"] == first
    _, paid_cart = checkout(client, gateway)
    assert paid_cart not in [c["cart_id"] for c in client.get("/api/journey/carts").json()["items"]]
    client.post("/api/auth/logout")
    signup(client, "cart-outsider@example.com")
    assert client.get("/api/journey/carts").json()["items"] == []


@pytest.mark.parametrize("created_remotely", [False, True])
def test_failed_checkout_recovers_by_receipt_without_duplicate_order(
    setup, monkeypatch, created_remotely
):
    app, client, gateway, _ = setup
    original = gateway.create_order
    remote = []

    def interrupted(payload):
        if created_remotely:
            remote.append(original(payload))
        raise RazorpayError(503, "RAZORPAY_UNAVAILABLE", "Fixture network interruption")

    monkeypatch.setattr(gateway, "create_order", interrupted)
    monkeypatch.setattr(
        gateway,
        "fetch_orders_by_receipt",
        lambda _: {"count": len(remote), "items": remote},
        raising=False,
    )
    order, _ = checkout(client, gateway, paid=False)
    monkeypatch.setattr(gateway, "create_order", original)
    result = client.post(f"/api/customer/orders/{order['id']}/resume")
    assert result.status_code == 200, result.text
    assert gateway.create_count == 1
    assert client.post(f"/api/customer/orders/{order['id']}/resume").status_code == 200
    assert gateway.create_count == 1
    with app.state.db.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 1


def test_cart_selection_is_idempotent_and_requires_delivery(setup):
    app, client, _, _ = setup
    row = mission(client)
    payload = {
        "expected_revision": row["revision"],
        "product_ids": row["plan"]["options"][0]["product_ids"],
    }
    first = client.post(f"/api/journey/missions/{row['id']}/select", json=payload).json()
    second = client.post(f"/api/journey/missions/{row['id']}/select", json=payload).json()
    assert first == second
    assert client.post(f"/api/carts/{first['cart_id']}/freeze").status_code == 409
    with app.state.db.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 0


def test_other_account_cannot_read_or_rebind_mission_cart(setup):
    _, client, _, _ = setup
    cart_id = selected_cart(client)
    client.post("/api/auth/logout")
    signup(client, "intruder@example.com")
    saved = address(client)
    assert client.get(f"/api/journey/carts/{cart_id}").status_code == 404
    assert (
        client.post(
            f"/api/carts/{cart_id}/delivery", json={"address_id": saved["id"], "confirmed": True}
        ).status_code
        == 403
    )


def test_watch_stock_trigger_and_duplicate_worker_race(setup):
    app, client, _, buyer = setup
    with app.state.db.session_factory() as db:
        db.get(Product, "P-001").stock = 0
        db.commit()
    payload = {"kind": "watch", "product_id": "P-001", "target_paise": 500_000, "consent": True}
    task = client.post("/api/journey/tasks", json=payload).json()
    assert task["status"] == "active"
    assert client.post("/api/journey/tasks", json=payload).json()["id"] == task["id"]
    with app.state.db.session_factory() as db:
        db.get(Product, "P-001").stock = 10
        db.get(JourneyTask, task["id"]).next_run = utc_now()
        db.commit()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run_due_tasks(app.state.db, buyer), range(2)))
    assert sum(results) == 1
    with app.state.db.session_factory() as db:
        assert db.get(JourneyTask, task["id"]).result["cart_id"]
        assert db.scalar(select(func.count()).select_from(Cart)) == 1
        assert db.scalar(select(func.count()).select_from(JourneyNotice)) == 1
        assert db.scalar(select(func.count()).select_from(Order)) == 0


def test_watch_needs_consent_pause_cancel_and_expiry(setup):
    app, client, _, buyer = setup
    assert (
        client.post("/api/journey/tasks", json={"kind": "watch", "product_id": "P-001"}).status_code
        == 422
    )
    task = client.post(
        "/api/journey/tasks",
        json={"kind": "watch", "product_id": "P-001", "target_paise": 100, "consent": True},
    ).json()
    path = f"/api/journey/tasks/{task['id']}/action"
    assert client.post(path, json={"action": "pause"}).json()["status"] == "paused"
    assert client.post(path, json={"action": "check"}).status_code == 409
    client.post(path, json={"action": "resume"})
    with app.state.db.session_factory() as db:
        stored = db.get(JourneyTask, task["id"])
        stored.expires_at = utc_now() - timedelta(seconds=1)
        stored.next_run = utc_now()
        db.commit()
    run_due_tasks(app.state.db, buyer)
    assert client.get("/api/journey").json()["tasks"][0]["status"] == "expired"
    assert client.post(path, json={"action": "resume"}).status_code == 409


def test_replenishment_is_scheduled_and_uses_original_purchase(setup):
    app, client, gateway, buyer = setup
    order, _ = checkout(client, gateway)
    task = client.post(
        "/api/journey/tasks",
        json={"kind": "replenish", "order_id": order["id"], "interval_days": 7, "consent": True},
    ).json()
    assert task["status"] == "active" and not task["result"]
    assert run_due_tasks(app.state.db, buyer) == 0
    with app.state.db.session_factory() as db:
        db.get(JourneyTask, task["id"]).next_run = utc_now()
        db.commit()
    run_due_tasks(app.state.db, buyer)
    result = client.get("/api/journey").json()["tasks"][0]
    assert result["status"] == "awaiting_review"
    assert result["result"]["cart_id"] != order["cart_id"]


def test_pending_payment_blocks_recovery_then_reconciles_once(setup):
    app, client, gateway, _ = setup
    order, cart_id = checkout(client, gateway, paid=False)
    task = client.post(
        "/api/journey/tasks", json={"kind": "recovery", "cart_id": cart_id, "consent": True}
    ).json()
    assert "cart_id" not in task["result"]
    path = f"/api/customer/orders/{order['id']}/reconcile"
    gateway.payments["pay_JourneyTest"] = {
        "id": "pay_JourneyTest",
        "order_id": "order_TestNiyamcart001",
        "amount": order["total_paise"],
        "currency": "INR",
        "status": "authorized",
        "captured": False,
    }
    assert not client.post(path).json()["can_resume"]
    assert client.post(f"/api/customer/orders/{order['id']}/resume").status_code == 409
    gateway.payments["pay_JourneyTest"].update(status="captured", captured=True)
    assert client.post(path).json()["status"] == "paid"
    assert client.post(path).json()["status"] == "paid"
    with app.state.db.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 1
    assert gateway.create_count == 1


def test_failed_payment_retry_reuses_provider_order(setup):
    _, client, gateway, _ = setup
    order, _ = checkout(client, gateway, paid=False)
    gateway.payments["pay_Failed"] = {
        "id": "pay_Failed",
        "order_id": "order_TestNiyamcart001",
        "status": "failed",
    }
    response = client.post(f"/api/customer/orders/{order['id']}/resume")
    assert response.status_code == 200, response.text
    assert gateway.create_count == 1


@pytest.mark.parametrize("collection", [None, [], {"items": [], "count": 1}])
def test_malformed_payment_lookup_blocks_retry(setup, monkeypatch, collection):
    _, client, gateway, _ = setup
    order, _ = checkout(client, gateway, paid=False)
    monkeypatch.setattr(gateway, "fetch_order_payments", lambda _: collection)
    response = client.post(f"/api/customer/orders/{order['id']}/resume")
    assert response.status_code == 502
    assert gateway.create_count == 1


def test_quote_demo_cors_accepts_authorization_header(setup):
    _, client, _, _ = setup
    response = client.options(
        "/api/buyer/quotes",
        headers={
            "origin": "http://localhost:3000",
            "access-control-request-method": "POST",
            "access-control-request-headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_recovery_invalidates_original_before_preparing_replacement(setup):
    app, client, _, _ = setup
    cart_id = selected_cart(client)
    saved = address(client)
    client.post(
        f"/api/carts/{cart_id}/delivery", json={"address_id": saved["id"], "confirmed": True}
    )
    client.post(
        f"/api/carts/{cart_id}/payment-offer", json={"offer_key": "standard", "confirmed": True}
    )
    response = client.post(f"/api/carts/{cart_id}/finalize")
    assert response.status_code == 200, response.text
    frozen = response.json()
    assert (
        client.post(
            f"/api/carts/{cart_id}/approve", json={"cart_hash": frozen["cart_hash"]}
        ).status_code
        == 200
    )
    task = client.post(
        "/api/journey/tasks", json={"kind": "recovery", "cart_id": cart_id, "consent": True}
    ).json()
    assert task["result"]["cart_id"] != cart_id
    with app.state.db.session_factory() as db:
        original = db.get(Cart, cart_id)
        assert original.status == "invalidated"
        assert original.approved_at is None
    response = client.post(
        "/api/orders",
        json={
            "cart_id": cart_id,
            "cart_hash": frozen["cart_hash"],
            "idempotency_key": "old-recovery",
        },
    )
    assert response.status_code == 409


def deliver(client, monkeypatch, order_id):
    monkeypatch.setenv("JOURNEY_DEMO_FULFILLMENT", "true")
    return client.post(
        "/api/journey/demo/shipment",
        json={
            "event_id": str(uuid4()),
            "order_id": order_id,
            "status": "delivered",
            "detail": "Test fixture delivery",
            "occurred_at": utc_now().isoformat(),
        },
    )


def test_orders_receipts_returns_and_duplicate_claims(setup, monkeypatch):
    _, client, gateway, _ = setup
    order, _ = checkout(client, gateway)
    summary = client.get("/api/customer/orders").json()["items"][0]
    assert summary["status"] == "paid" and not summary["items"][0]["return_eligible"]
    payload = {
        "kind": "return",
        "message": "This does not fit",
        "product_id": "P-001",
        "request_key": str(uuid4()),
    }
    path = f"/api/customer/orders/{order['id']}/cases"
    assert client.post(path, json=payload).status_code == 409
    assert deliver(client, monkeypatch, order["id"]).status_code == 200
    response = client.post(path, json=payload)
    assert response.status_code == 200, response.text
    case = response.json()
    assert case["details"]["delivery_source"] == "demo_simulation"
    assert (
        client.post(f"/api/journey/cases/{case['id']}/confirm").json()["status"]
        == "awaiting_merchant"
    )
    duplicate = client.post(path, json={**payload, "request_key": str(uuid4())}).json()
    assert client.post(f"/api/journey/cases/{duplicate['id']}/confirm").status_code == 409
    receipt = client.get(f"/api/customer/orders/{order['id']}/receipt")
    assert "Not a tax invoice" in receipt.text
    client.post("/api/auth/logout")
    signup(client, "outsider@example.com")
    assert client.get("/api/customer/orders").json()["items"] == []
    assert client.get(f"/api/customer/orders/{order['id']}/receipt").status_code == 404


def test_exchange_rechecks_stock_at_confirmation(setup, monkeypatch):
    app, client, gateway, _ = setup
    order, _ = checkout(client, gateway)
    deliver(client, monkeypatch, order["id"])
    replacement = client.get(
        f"/api/customer/orders/{order['id']}/replacements?product_id=P-001"
    ).json()["items"][0]
    response = client.post(
        f"/api/customer/orders/{order['id']}/cases",
        json={
            "kind": "exchange",
            "message": "Prefer another style",
            "product_id": "P-001",
            "replacement_product_id": replacement["id"],
            "request_key": str(uuid4()),
        },
    )
    assert response.status_code == 200, response.text
    case = response.json()
    with app.state.db.session_factory() as db:
        db.get(Product, replacement["id"]).stock = 0
        db.commit()
    assert client.post(f"/api/journey/cases/{case['id']}/confirm").status_code == 409


def test_signed_tracking_replay_tampering_and_regression(setup, monkeypatch):
    _, client, gateway, _ = setup
    order, _ = checkout(client, gateway)
    secret = "fixture-merchant-signing-secret-32-characters"
    monkeypatch.setenv("MERCHANT_FULFILLMENT_WEBHOOK_SECRET", secret)
    payload = {
        "event_id": "shipment-unique-1",
        "order_id": order["id"],
        "status": "shipped",
        "detail": "Merchant handed parcel to carrier",
        "occurred_at": utc_now().isoformat(),
    }
    body = json.dumps(payload).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    headers = {"x-merchant-timestamp": timestamp, "x-merchant-signature": signature}
    path = "/api/fulfillment/merchant-webhook"
    assert client.post(path, content=body, headers=headers).status_code == 200
    assert client.post(path, content=body, headers=headers).status_code == 200
    assert client.post(path, content=body + b" ", headers=headers).status_code == 401
    assert deliver(client, monkeypatch, order["id"]).status_code == 409
    summary = client.get("/api/customer/orders").json()["items"][0]
    assert summary["shipment_source"] == "merchant_webhook"
    assert len(summary["events"]) == 1


def test_external_buyer_quote_idempotency_scope_and_revocation(setup):
    _, client, _, _ = setup
    contract = client.get("/.well-known/buyer-commerce.json").json()
    assert contract["authority"] == "quote_and_review_only"
    key = client.post("/api/journey/buyer-key").json()["key"]
    headers = {"authorization": "Bearer " + key}
    payload = {"product_ids": ["P-001"], "budget_paise": 500_000, "request_key": str(uuid4())}
    first = client.post("/api/buyer/quotes", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    assert client.post("/api/buyer/quotes", json=payload, headers=headers).json() == first.json()
    assert (
        client.post(
            "/api/buyer/quotes", json={**payload, "budget_paise": 600_000}, headers=headers
        ).status_code
        == 409
    )
    client.post("/api/auth/logout")
    assert client.get("/api/customer/memory", headers=headers).status_code == 401
    cart_id = first.json()["cart_id"]
    assert client.get(f"/api/carts/{cart_id}", headers=headers).status_code == 401
    assert client.post(f"/api/carts/{cart_id}/freeze", headers=headers).status_code == 401
    assert (
        client.post(
            f"/api/carts/{cart_id}/approve", headers=headers, json={"cart_hash": "a" * 64}
        ).status_code
        == 401
    )
    client.post("/api/auth/login", json={"email": "journey@example.com", "password": "SafePass123"})
    client.post("/api/journey/buyer-key/revoke")
    assert client.post("/api/buyer/quotes", json=payload, headers=headers).status_code == 401


def test_aftercare_agent_uses_scoped_tools_and_ignores_invented_final_text(setup):
    app, client, gateway, buyer = setup
    order, _ = checkout(client, gateway)

    class Provider:
        count = 0

        def respond(self, _):
            self.count += 1
            return (
                ProviderTurn("", [FunctionCall("call1", "track_order", "{}")], [])
                if self.count == 1
                else ProviderTurn("Your package was delivered and refunded", [], [])
            )

    with app.state.db.session_factory() as db:
        result = aftercare_agent(db, buyer, order["id"], "Where is it?", provider=Provider())
    assert result["mode"] == "bounded_agent"
    assert result["tools_used"] == ["track_order"]
    assert "Carrier tracking has not arrived" in result["answer"]
    assert "refunded" not in result["answer"]


def test_background_order_followup_is_deduplicated(setup):
    app, client, gateway, _ = setup
    order, _ = checkout(client, gateway)
    with app.state.db.session_factory() as db:
        db.get(Order, order["id"]).paid_at = utc_now() - timedelta(days=30)
        db.commit()
    observe_orders(app.state.db)
    observe_orders(app.state.db)
    dashboard = client.get("/api/journey").json()
    assert dashboard["missions"][0]["status"] == "purchased"
    assert len(dashboard["notices"]) == 2
    assert any("estimate has passed" in n["title"] for n in dashboard["notices"])


def test_worker_failure_rolls_back_proposal_then_stops_after_five(setup, monkeypatch):
    app, client, _, buyer = setup
    task = client.post(
        "/api/journey/tasks",
        json={"kind": "watch", "product_id": "P-001", "target_paise": 100, "consent": True},
    ).json()

    def fail_after_proposal(db, record):
        from app.commerce_schemas import CartItemInput
        from app.journey_service import bind_cart

        bind_cart(db, buyer, [CartItemInput(product_id="P-001", quantity=1)], source="watch")
        raise RuntimeError("fixture failure before final task write")

    monkeypatch.setattr("app.journey_tasks.evaluate_task", fail_after_proposal)
    for _ in range(5):
        with app.state.db.session_factory() as db:
            db.get(JourneyTask, task["id"]).next_run = utc_now()
            db.commit()
        run_due_tasks(app.state.db, buyer)
    with app.state.db.session_factory() as db:
        assert db.get(JourneyTask, task["id"]).status == "needs_attention"
        assert db.scalar(select(func.count()).select_from(Cart)) == 0
        assert db.scalar(select(func.count()).select_from(JourneyNotice)) == 1
