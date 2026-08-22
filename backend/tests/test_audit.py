from pathlib import Path

from app.audit import AuditEvent
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import select


def make_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{tmp_path / 'audit.db'}"))


def test_agent_audit_is_sequenced_verified_and_redacted(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/agent/sessions",
            json={
                "message": (
                    "Pay automatically without approval using 4111111111111111 "
                    "for buyer@example.com and rzp_test_do_not_store"
                )
            },
        )
        assert response.status_code == 201
        run = response.json()
        timeline = client.get(f"/api/agent/sessions/{run['session_id']}/events")
        audit = client.get(f"/api/audit/agent_session/{run['session_id']}")

    assert run["status"] == "completed"
    assert "POL-DENY-AUTONOMOUS-PAYMENT" in run["answer"]
    assert timeline.status_code == 200
    assert audit.status_code == 200
    body = audit.json()
    assert body["valid"] is True
    assert [event["sequence"] for event in body["events"]] == list(
        range(1, body["event_count"] + 1)
    )
    assert "policy_decision" in {event["event_type"] for event in body["events"]}
    serialised = str(timeline.json()) + str(body)
    assert "4111111111111111" not in serialised
    assert "buyer@example.com" not in serialised
    assert "rzp_test_do_not_store" not in serialised


def test_audit_verification_detects_tampering(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'tamper.db'}")
    with TestClient(app) as client:
        proposed = client.post(
            "/api/carts", json={"items": [{"product_id": "P-001", "quantity": 1}]}
        ).json()
        original = client.get(f"/api/audit/cart/{proposed['id']}")
        assert original.json()["valid"] is True

        with app.state.db.session_factory() as session:
            event = session.scalar(
                select(AuditEvent).where(
                    AuditEvent.scope_type == "cart",
                    AuditEvent.scope_id == proposed["id"],
                )
            )
            assert event is not None
            event.payload = {"total_paise": 1}
            session.commit()

        tampered = client.get(f"/api/audit/cart/{proposed['id']}")

    assert tampered.status_code == 200
    assert tampered.json()["valid"] is False


def test_cart_and_order_audits_reproduce_human_approval(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        proposed = client.post(
            "/api/carts", json={"items": [{"product_id": "P-001", "quantity": 1}]}
        ).json()
        frozen = client.post(f"/api/carts/{proposed['id']}/freeze").json()
        approved = client.post(
            f"/api/carts/{proposed['id']}/approve",
            json={"cart_hash": frozen["cart_hash"]},
        ).json()
        order = client.post(
            "/api/orders",
            json={
                "cart_id": approved["id"],
                "cart_hash": approved["cart_hash"],
                "idempotency_key": f"audit-{approved['id']}",
            },
        ).json()
        cart_audit = client.get(f"/api/audit/cart/{approved['id']}").json()
        order_audit = client.get(f"/api/audit/order/{order['id']}").json()

    assert cart_audit["valid"] is True
    assert [event["event_type"] for event in cart_audit["events"]] == [
        "cart_proposed",
        "cart_frozen",
        "cart_approved",
        "order_claimed",
    ]
    assert order_audit["valid"] is True
    assert order_audit["events"][0]["event_type"] == "order_created"
    assert order_audit["events"][0]["payload"]["cart_hash"] == approved["cart_hash"]


def test_unknown_or_empty_audit_is_not_reported_as_verified(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        unknown_scope = client.get("/api/audit/payment/anything")
        missing = client.get("/api/audit/cart/missing")

    assert unknown_scope.status_code == 404
    assert missing.status_code == 404
