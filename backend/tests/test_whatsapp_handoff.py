from pathlib import Path

from app.commerce import PaymentEvidence, bind_provider_order, finalise_payment
from app.main import create_app
from app.whatsapp_delivery import WhatsAppDelivery
from app.whatsapp_models import WhatsAppHandoff
from app.whatsapp_service import WhatsAppSettings
from fastapi.testclient import TestClient
from sqlalchemy import select

ENABLED = WhatsAppSettings(
    enabled=True,
    public_app_url="https://shop.example.test",
    link_secret="local-test-signing-secret-with-32-characters",
)
DESTINATION = "+919876543210"


def review_request(cart: dict[str, object], *, consent: bool = True) -> dict[str, object]:
    return {
        "cart_hash": cart["cart_hash"],
        "destination": DESTINATION,
        "consent": consent,
        "destination_confirmed": True,
    }


CONFIRMATION_REQUEST = {
    "destination": DESTINATION,
    "consent": True,
    "destination_confirmed": True,
}


class RecordingSender:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def send(self, **payload: object) -> WhatsAppDelivery:
        self.calls.append(payload)
        return WhatsAppDelivery("SM00000000000000000000000000000000", "queued")


def frozen_cart(client: TestClient) -> dict[str, object]:
    proposed = client.post(
        "/api/carts", json={"items": [{"product_id": "P-001", "quantity": 1}]}
    ).json()
    return client.post(f"/api/carts/{proposed['id']}/freeze").json()


def test_disabled_handoff_keeps_core_in_app_flow_available(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{tmp_path / 'disabled.db'}",
        whatsapp_settings=WhatsAppSettings(enabled=False),
    )
    with TestClient(app) as client:
        cart = frozen_cart(client)
        response = client.post(
            f"/api/carts/{cart['id']}/whatsapp-review",
            json=review_request(cart),
        )

    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    assert response.json()["review_url"] is None


def test_review_handoff_requires_opt_in_is_idempotent_and_never_approves(
    tmp_path: Path,
) -> None:
    app = create_app(
        f"sqlite:///{tmp_path / 'review.db'}",
        whatsapp_settings=ENABLED,
    )
    with TestClient(app) as client:
        cart = frozen_cart(client)
        missing_consent = client.post(
            f"/api/carts/{cart['id']}/whatsapp-review",
            json=review_request(cart, consent=False),
        )
        first = client.post(
            f"/api/carts/{cart['id']}/whatsapp-review",
            json=review_request(cart),
        )
        duplicate = client.post(
            f"/api/carts/{cart['id']}/whatsapp-review",
            json=review_request(cart),
        )
        token = first.json()["review_url"].rsplit("/", 1)[-1]
        review = client.get(f"/api/notifications/whatsapp/review/{token}")
        stored = client.get(f"/api/carts/{cart['id']}")

    assert missing_consent.status_code == 422
    assert first.json()["status"] == "ready_for_user_share"
    assert first.json()["duplicate"] is False
    assert duplicate.json()["duplicate"] is True
    assert "Approval and payment happen only in NiyamCart" in first.json()["share_text"]
    assert review.status_code == 200
    assert review.json()["permits_financial_approval"] is False
    assert review.json()["cart"]["cart_hash"] == cart["cart_hash"]
    assert stored.json()["status"] == "frozen"


def test_tampered_review_link_is_rejected(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{tmp_path / 'tampered-link.db'}",
        whatsapp_settings=ENABLED,
    )
    with TestClient(app) as client:
        cart = frozen_cart(client)
        handoff = client.post(
            f"/api/carts/{cart['id']}/whatsapp-review",
            json=review_request(cart),
        ).json()
        token = handoff["review_url"].rsplit("/", 1)[-1]
        response = client.get(f"/api/notifications/whatsapp/review/{token[:-1]}x")

    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_REVIEW_LINK"


def test_confirmation_is_available_only_after_backend_verified_payment(
    tmp_path: Path,
) -> None:
    app = create_app(
        f"sqlite:///{tmp_path / 'confirmation.db'}",
        whatsapp_settings=ENABLED,
    )
    with TestClient(app) as client:
        cart = frozen_cart(client)
        client.post(
            f"/api/carts/{cart['id']}/whatsapp-review",
            json=review_request(cart),
        )
        client.post(
            f"/api/carts/{cart['id']}/approve",
            json={"cart_hash": cart["cart_hash"]},
        )
        order = client.post(
            "/api/orders",
            json={
                "cart_id": cart["id"],
                "cart_hash": cart["cart_hash"],
                "idempotency_key": f"whatsapp-{cart['id']}",
            },
        ).json()
        before = client.post(
            f"/api/orders/{order['id']}/whatsapp-confirmation",
            json=CONFIRMATION_REQUEST,
        )

        with app.state.db.session_factory() as session:
            bind_provider_order(session, order["id"], "order_whatsapp_test")
            finalise_payment(
                session,
                order["id"],
                PaymentEvidence(
                    provider_event_id="event_whatsapp_verified",
                    event_type="payment.captured",
                    provider_order_id="order_whatsapp_test",
                    provider_payment_id="pay_whatsapp_test",
                    amount_paise=order["total_paise"],
                    currency="INR",
                    signature_verified=True,
                    captured=True,
                ),
            )

        first = client.post(
            f"/api/orders/{order['id']}/whatsapp-confirmation",
            json=CONFIRMATION_REQUEST,
        )
        duplicate = client.post(
            f"/api/orders/{order['id']}/whatsapp-confirmation",
            json=CONFIRMATION_REQUEST,
        )
        with app.state.db.session_factory() as session:
            handoffs = list(session.scalars(select(WhatsAppHandoff)))

    assert before.status_code == 409
    assert before.json()["error"] == "PAYMENT_NOT_VERIFIED"
    assert first.status_code == 200
    assert "payment was verified" in first.json()["share_text"]
    assert duplicate.json()["duplicate"] is True
    assert len(handoffs) == 2


def test_external_delivery_requires_confirmed_destination_is_idempotent_and_stores_no_phone(
    tmp_path: Path,
) -> None:
    sender = RecordingSender()
    app = create_app(
        f"sqlite:///{tmp_path / 'external-delivery.db'}",
        whatsapp_settings=ENABLED,
        whatsapp_sender=sender,
    )
    with TestClient(app) as client:
        cart = frozen_cart(client)
        missing_confirmation = client.post(
            f"/api/carts/{cart['id']}/whatsapp-review",
            json={
                "cart_hash": cart["cart_hash"],
                "destination": DESTINATION,
                "consent": True,
                "destination_confirmed": False,
            },
        )
        first = client.post(
            f"/api/carts/{cart['id']}/whatsapp-review",
            json=review_request(cart),
        )
        duplicate = client.post(
            f"/api/carts/{cart['id']}/whatsapp-review",
            json=review_request(cart),
        )
        with app.state.db.session_factory() as session:
            stored = session.scalar(select(WhatsAppHandoff))

    assert missing_confirmation.status_code == 422
    assert first.json()["status"] == "sent"
    assert first.json()["destination_fingerprint"]
    assert duplicate.json()["duplicate"] is True
    assert len(sender.calls) == 1
    assert stored is not None
    assert DESTINATION not in str(stored.payload)
