from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest
from app.commerce import (
    CommerceError,
    PaymentEvidence,
    approve_cart,
    bind_provider_order,
    create_cart,
    create_order,
    finalise_payment,
    freeze_cart,
)
from app.commerce_schemas import CreateCartRequest, CreateOrderRequest
from app.database import Base
from app.main import create_app
from app.models import Product
from fastapi.testclient import TestClient
from sqlalchemy import Integer


def make_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{tmp_path / 'commerce.db'}"))


def proposed_payload() -> dict[str, object]:
    return {
        "items": [
            {"product_id": "P-001", "quantity": 2},
            {"product_id": "P-351", "quantity": 1},
        ]
    }


def create_approved_cart(client: TestClient) -> dict[str, object]:
    proposed = client.post("/api/carts", json=proposed_payload())
    assert proposed.status_code == 201
    frozen = client.post(f"/api/carts/{proposed.json()['id']}/freeze")
    assert frozen.status_code == 200
    approved = client.post(
        f"/api/carts/{frozen.json()['id']}/approve",
        json={"cart_hash": frozen.json()["cart_hash"]},
    )
    assert approved.status_code == 200
    return approved.json()


def create_pending_order(
    client: TestClient, key: str = "checkout-attempt-0001"
) -> dict[str, object]:
    cart = create_approved_cart(client)
    response = client.post(
        "/api/orders",
        json={"cart_id": cart["id"], "cart_hash": cart["cart_hash"], "idempotency_key": key},
    )
    assert response.status_code == 201
    return response.json()


def test_exact_cart_approval_and_idempotent_order(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        cart = create_approved_cart(client)
        assert cart["total_paise"] == 82_700
        assert cart["currency"] == "INR"
        assert len(cart["cart_hash"]) == 64

        request = {
            "cart_id": cart["id"],
            "cart_hash": cart["cart_hash"],
            "idempotency_key": "checkout-attempt-0001",
        }
        first = client.post("/api/orders", json=request)
        duplicate = client.post("/api/orders", json=request)

    assert first.status_code == 201
    assert duplicate.status_code == 201
    assert first.json()["id"] == duplicate.json()["id"]
    assert first.json()["total_paise"] == cart["total_paise"]
    assert first.json()["status"] == "payment_pending"


def test_wrong_hash_and_invalid_state_are_rejected(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        proposed = client.post("/api/carts", json=proposed_payload()).json()
        premature = client.post(
            f"/api/carts/{proposed['id']}/approve",
            json={"cart_hash": "0" * 64},
        )
        frozen = client.post(f"/api/carts/{proposed['id']}/freeze").json()
        wrong_hash = client.post(
            f"/api/carts/{proposed['id']}/approve",
            json={"cart_hash": "f" * 64},
        )

    assert premature.status_code == 409
    assert premature.json()["error"] == "INVALID_CART_STATE"
    assert frozen["status"] == "frozen"
    assert wrong_hash.status_code == 409
    assert wrong_hash.json()["error"] == "CART_HASH_MISMATCH"


def test_expired_cart_requires_new_review(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'expired.db'}")
    with TestClient(app):
        fixed_now = datetime(2026, 8, 22, 12, 0, 0)
        with app.state.db.session_factory() as session:
            cart = create_cart(session, CreateCartRequest.model_validate(proposed_payload()))
            frozen = freeze_cart(session, cart.id, now=fixed_now)
            with pytest.raises(CommerceError, match="expired") as caught:
                approve_cart(
                    session,
                    frozen.id,
                    frozen.cart_hash or "",
                    now=fixed_now + timedelta(minutes=16),
                )
            assert caught.value.code == "CART_EXPIRED"


def test_price_change_invalidates_approval(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'changed.db'}")
    with TestClient(app) as client:
        cart = create_approved_cart(client)
        with app.state.db.session_factory() as session:
            product = session.get(Product, "P-001")
            assert product is not None
            product.price_paise += 100
            product.version += 1
            session.commit()

        order = client.post(
            "/api/orders",
            json={
                "cart_id": cart["id"],
                "cart_hash": cart["cart_hash"],
                "idempotency_key": "changed-price-attempt",
            },
        )
        refreshed = client.get(f"/api/carts/{cart['id']}")

    assert order.status_code == 409
    assert order.json()["error"] == "CART_CHANGED"
    assert refreshed.json()["status"] == "invalidated"


def test_payment_finalisation_is_verified_and_duplicate_safe(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'payment.db'}")
    with TestClient(app) as client:
        pending = create_pending_order(client)
        with app.state.db.session_factory() as session:
            bind_provider_order(session, pending["id"], "order_test_001")
            evidence = PaymentEvidence(
                provider_event_id="event_test_001",
                event_type="payment.captured",
                provider_order_id="order_test_001",
                provider_payment_id="pay_test_001",
                amount_paise=pending["total_paise"],
                currency="INR",
                signature_verified=True,
                captured=True,
            )
            first_order, first_event = finalise_payment(session, pending["id"], evidence)
            duplicate_order, duplicate_event = finalise_payment(session, pending["id"], evidence)

    assert first_order.status == "paid"
    assert first_event.accepted is True
    assert duplicate_order.status == "paid"
    assert duplicate_event.provider_event_id == first_event.provider_event_id


def test_invalid_amount_cannot_mark_order_paid(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'invalid-payment.db'}")
    with TestClient(app) as client:
        pending = create_pending_order(client)
        with app.state.db.session_factory() as session:
            bind_provider_order(session, pending["id"], "order_test_002")
            evidence = PaymentEvidence(
                provider_event_id="event_test_bad_amount",
                event_type="payment.captured",
                provider_order_id="order_test_002",
                provider_payment_id="pay_test_bad_amount",
                amount_paise=pending["total_paise"] - 1,
                currency="INR",
                signature_verified=True,
                captured=True,
            )
            order, event = finalise_payment(session, pending["id"], evidence)

    assert event.accepted is False
    assert event.reason == "amount_or_currency_mismatch"
    assert order.status == "payment_pending"


def test_idempotency_key_cannot_be_reused_for_another_cart(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'idempotency.db'}")
    with TestClient(app):
        with app.state.db.session_factory() as session:
            first_cart = create_cart(session, CreateCartRequest.model_validate(proposed_payload()))
            first_frozen = freeze_cart(session, first_cart.id)
            first_approved = approve_cart(session, first_cart.id, first_frozen.cart_hash or "")
            create_order(
                session,
                CreateOrderRequest(
                    cart_id=first_approved.id,
                    cart_hash=first_approved.cart_hash or "",
                    idempotency_key="shared-idempotency-key",
                ),
            )

            second_cart = create_cart(session, CreateCartRequest.model_validate(proposed_payload()))
            second_frozen = freeze_cart(session, second_cart.id)
            second_approved = approve_cart(session, second_cart.id, second_frozen.cart_hash or "")
            with pytest.raises(CommerceError) as caught:
                create_order(
                    session,
                    CreateOrderRequest(
                        cart_id=second_approved.id,
                        cart_hash=second_approved.cart_hash or "",
                        idempotency_key="shared-idempotency-key",
                    ),
                )

    assert caught.value.code == "IDEMPOTENCY_KEY_REUSED"


def test_concurrent_identical_order_requests_converge(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'order-race.db'}")
    with TestClient(app) as client:
        cart = create_approved_cart(client)
        request = CreateOrderRequest(
            cart_id=str(cart["id"]),
            cart_hash=str(cart["cart_hash"]),
            idempotency_key="concurrent-order-attempt",
        )
        barrier = Barrier(2)

        def worker() -> str:
            with app.state.db.session_factory() as session:
                barrier.wait()
                return create_order(session, request).id

        with ThreadPoolExecutor(max_workers=2) as executor:
            order_ids = list(executor.map(lambda _: worker(), range(2)))

    assert len(set(order_ids)) == 1


def test_concurrent_duplicate_payment_events_converge(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'payment-race.db'}")
    with TestClient(app) as client:
        pending = create_pending_order(client, key="payment-race-order")
        with app.state.db.session_factory() as session:
            bind_provider_order(session, str(pending["id"]), "order_race_001")

        evidence = PaymentEvidence(
            provider_event_id="event_race_001",
            event_type="payment.captured",
            provider_order_id="order_race_001",
            provider_payment_id="pay_race_001",
            amount_paise=int(pending["total_paise"]),
            currency="INR",
            signature_verified=True,
            captured=True,
        )
        barrier = Barrier(2)

        def worker() -> tuple[str, bool]:
            with app.state.db.session_factory() as session:
                barrier.wait()
                order, event = finalise_payment(session, str(pending["id"]), evidence)
                return order.status, event.accepted

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: worker(), range(2)))

    assert results == [("paid", True), ("paid", True)]


def test_every_money_column_uses_integer_storage() -> None:
    money_markers = ("price", "amount", "total", "subtotal")
    money_columns = [
        column
        for table in Base.metadata.tables.values()
        for column in table.columns
        if any(marker in column.name for marker in money_markers)
    ]

    assert money_columns
    assert all(isinstance(column.type, Integer) for column in money_columns)


def test_public_api_has_no_raw_card_fields(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        schema = client.get("/openapi.json").text.lower()

    assert "card_number" not in schema
    assert "cvv" not in schema
