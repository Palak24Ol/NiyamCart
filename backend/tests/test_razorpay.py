import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from app.main import create_app
from app.razorpay_service import RazorpayError, RazorpaySettings
from fastapi.testclient import TestClient


class FakeRazorpayGateway:
    key_id = "rzp_test_niyamcart"
    key_secret = "checkout-test-secret"
    webhook_secret = "webhook-test-secret"

    def __init__(self) -> None:
        self.create_count = 0
        self.fetch_count = 0
        self.fail_creation = False
        self.last_order_payload: dict[str, object] | None = None
        self.payments: dict[str, dict[str, object]] = {}

    def create_order(self, payload: dict[str, object]) -> dict[str, object]:
        self.create_count += 1
        self.last_order_payload = payload
        if self.fail_creation:
            raise RazorpayError(503, "RAZORPAY_UNAVAILABLE", "provider unavailable")
        return {
            "id": "order_TestNiyamcart001",
            "amount": payload["amount"],
            "currency": payload["currency"],
            "receipt": payload["receipt"],
            "status": "created",
        }

    def fetch_payment(self, payment_id: str) -> dict[str, object]:
        self.fetch_count += 1
        return self.payments[payment_id]

    def verify_checkout_signature(
        self, provider_order_id: str, payment_id: str, signature: str
    ) -> bool:
        expected = hmac.new(
            self.key_secret.encode(),
            f"{provider_order_id}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        expected = hmac.new(
            self.webhook_secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def checkout_signature(self, order_id: str, payment_id: str) -> str:
        return hmac.new(
            self.key_secret.encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()

    def webhook_signature(self, raw_body: bytes) -> str:
        return hmac.new(
            self.webhook_secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()


def make_client(tmp_path: Path, gateway: FakeRazorpayGateway) -> TestClient:
    return TestClient(
        create_app(
            f"sqlite:///{tmp_path / 'razorpay.db'}",
            razorpay_gateway=gateway,
        )
    )


def create_internal_order(client: TestClient) -> dict[str, object]:
    proposed = client.post(
        "/api/carts", json={"items": [{"product_id": "P-001", "quantity": 1}]}
    ).json()
    frozen = client.post(f"/api/carts/{proposed['id']}/freeze").json()
    approved = client.post(
        f"/api/carts/{frozen['id']}/approve",
        json={"cart_hash": frozen["cart_hash"]},
    ).json()
    response = client.post(
        "/api/orders",
        json={
            "cart_id": approved["id"],
            "cart_hash": approved["cart_hash"],
            "idempotency_key": f"checkout-{approved['id']}",
        },
    )
    assert response.status_code == 201
    return response.json()


def open_checkout(
    client: TestClient, gateway: FakeRazorpayGateway
) -> tuple[dict[str, object], dict[str, object]]:
    order = create_internal_order(client)
    response = client.post(f"/api/orders/{order['id']}/razorpay-checkout")
    assert response.status_code == 201
    return order, response.json()


def captured_payment(
    checkout: dict[str, object], payment_id: str = "pay_TestNiyamcart001"
) -> dict[str, object]:
    return {
        "id": payment_id,
        "entity": "payment",
        "amount": checkout["amount_paise"],
        "currency": checkout["currency"],
        "status": "captured",
        "order_id": checkout["razorpay_order_id"],
        "captured": True,
    }


def test_checkout_creates_exactly_one_bound_test_order(tmp_path: Path) -> None:
    gateway = FakeRazorpayGateway()
    with make_client(tmp_path, gateway) as client:
        order, first = open_checkout(client, gateway)
        second = client.post(f"/api/orders/{order['id']}/razorpay-checkout")

    assert second.status_code == 201
    assert second.json() == first
    assert gateway.create_count == 1
    assert first["test_mode"] is True
    assert first["key_id"].startswith("rzp_test_")
    assert gateway.last_order_payload == {
        "amount": order["total_paise"],
        "currency": "INR",
        "receipt": f"nc-{order['id']}",
        "notes": {
            "internal_order_id": order["id"],
            "cart_hash": order["cart_hash"],
            "mode": "test",
        },
    }


def test_checkout_callback_fetches_and_reconciles_captured_payment(tmp_path: Path) -> None:
    gateway = FakeRazorpayGateway()
    with make_client(tmp_path, gateway) as client:
        order, checkout = open_checkout(client, gateway)
        payment_id = "pay_TestCallback001"
        gateway.payments[payment_id] = captured_payment(checkout, payment_id)
        payload = {
            "internal_order_id": order["id"],
            "razorpay_order_id": checkout["razorpay_order_id"],
            "razorpay_payment_id": payment_id,
            "razorpay_signature": gateway.checkout_signature(
                str(checkout["razorpay_order_id"]), payment_id
            ),
        }
        first = client.post("/api/payments/razorpay/verify", json=payload)
        duplicate = client.post("/api/payments/razorpay/verify", json=payload)
        stored = client.get(f"/api/orders/{order['id']}")

    assert first.status_code == 200
    assert first.json()["payment_status"] == "verified"
    assert first.json()["duplicate"] is False
    assert first.json()["internal_order_id"] == order["id"]
    assert first.json()["razorpay_payment_id"] == payment_id
    assert first.json()["amount_paise"] == order["total_paise"]
    assert first.json()["currency"] == "INR"
    assert first.json()["verified_at"]
    assert first.json()["test_mode"] is True
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    assert gateway.fetch_count == 1
    assert stored.json()["status"] == "paid"
    assert stored.json()["provider_payment_id"] == payment_id


def test_invalid_checkout_signature_never_fetches_or_pays(tmp_path: Path) -> None:
    gateway = FakeRazorpayGateway()
    with make_client(tmp_path, gateway) as client:
        order, checkout = open_checkout(client, gateway)
        response = client.post(
            "/api/payments/razorpay/verify",
            json={
                "internal_order_id": order["id"],
                "razorpay_order_id": checkout["razorpay_order_id"],
                "razorpay_payment_id": "pay_TestBadSignature",
                "razorpay_signature": "0" * 64,
            },
        )
        stored = client.get(f"/api/orders/{order['id']}")

    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_PAYMENT_SIGNATURE"
    assert gateway.fetch_count == 0
    assert stored.json()["status"] == "payment_pending"


def test_fetched_amount_mismatch_is_recorded_but_not_paid(tmp_path: Path) -> None:
    gateway = FakeRazorpayGateway()
    with make_client(tmp_path, gateway) as client:
        order, checkout = open_checkout(client, gateway)
        payment_id = "pay_TestWrongAmount"
        gateway.payments[payment_id] = {
            **captured_payment(checkout, payment_id),
            "amount": int(checkout["amount_paise"]) - 1,
        }
        response = client.post(
            "/api/payments/razorpay/verify",
            json={
                "internal_order_id": order["id"],
                "razorpay_order_id": checkout["razorpay_order_id"],
                "razorpay_payment_id": payment_id,
                "razorpay_signature": gateway.checkout_signature(
                    str(checkout["razorpay_order_id"]), payment_id
                ),
            },
        )
        stored = client.get(f"/api/orders/{order['id']}")

    assert response.status_code == 409
    assert response.json()["error"] == "PAYMENT_NOT_VERIFIED"
    assert "amount_or_currency_mismatch" in response.json()["message"]
    assert stored.json()["status"] == "payment_pending"


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"order_id": "order_OtherProviderOrder"}, "provider_order_mismatch"),
        ({"currency": "USD"}, "amount_or_currency_mismatch"),
        ({"status": "authorized", "captured": False}, "payment_not_captured"),
    ],
)
def test_fetched_payment_must_match_every_authoritative_field(
    tmp_path: Path, overrides: dict[str, object], reason: str
) -> None:
    gateway = FakeRazorpayGateway()
    with make_client(tmp_path, gateway) as client:
        order, checkout = open_checkout(client, gateway)
        payment_id = f"pay_FieldCheck{reason.replace('_', '').title()}"
        gateway.payments[payment_id] = {**captured_payment(checkout, payment_id), **overrides}
        response = client.post(
            "/api/payments/razorpay/verify",
            json={
                "internal_order_id": order["id"],
                "razorpay_order_id": checkout["razorpay_order_id"],
                "razorpay_payment_id": payment_id,
                "razorpay_signature": gateway.checkout_signature(
                    str(checkout["razorpay_order_id"]), payment_id
                ),
            },
        )
        stored = client.get(f"/api/orders/{order['id']}")

    assert response.status_code == 409
    assert reason in response.json()["message"]
    assert stored.json()["status"] == "payment_pending"


def webhook_payload(
    event_type: str, checkout: dict[str, object], payment_id: str
) -> bytes:
    return json.dumps(
        {
            "entity": "event",
            "event": event_type,
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "order_id": checkout["razorpay_order_id"],
                        "amount": checkout["amount_paise"],
                        "currency": checkout["currency"],
                        "status": "failed" if event_type == "payment.failed" else "captured",
                        "captured": event_type != "payment.failed",
                    }
                }
            },
        },
        separators=(",", ":"),
    ).encode()


def send_webhook(
    client: TestClient,
    gateway: FakeRazorpayGateway,
    raw_body: bytes,
    event_id: str,
):
    return client.post(
        "/api/payments/razorpay/webhook",
        content=raw_body,
        headers={
            "content-type": "application/json",
            "x-razorpay-event-id": event_id,
            "x-razorpay-signature": gateway.webhook_signature(raw_body),
        },
    )


def test_webhook_uses_raw_signature_fetches_truth_and_deduplicates(tmp_path: Path) -> None:
    gateway = FakeRazorpayGateway()
    with make_client(tmp_path, gateway) as client:
        order, checkout = open_checkout(client, gateway)
        payment_id = "pay_TestWebhook001"
        gateway.payments[payment_id] = captured_payment(checkout, payment_id)
        raw_body = webhook_payload("payment.captured", checkout, payment_id)
        first = send_webhook(client, gateway, raw_body, "event_test_captured_001")
        duplicate = send_webhook(client, gateway, raw_body, "event_test_captured_001")
        stored = client.get(f"/api/orders/{order['id']}")

    assert first.status_code == 200
    assert first.json() == {
        "status": "ok",
        "duplicate": False,
        "processed": True,
        "reason": "verified",
    }
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    assert gateway.fetch_count == 1
    assert stored.json()["status"] == "paid"


def test_out_of_order_failed_and_captured_webhooks_do_not_regress_state(
    tmp_path: Path,
) -> None:
    gateway = FakeRazorpayGateway()
    with make_client(tmp_path, gateway) as client:
        order, checkout = open_checkout(client, gateway)
        payment_id = "pay_TestOutOfOrder"
        failed_body = webhook_payload("payment.failed", checkout, payment_id)
        failed_first = send_webhook(client, gateway, failed_body, "event_failed_first")
        pending = client.get(f"/api/orders/{order['id']}")

        gateway.payments[payment_id] = captured_payment(checkout, payment_id)
        captured_body = webhook_payload("payment.captured", checkout, payment_id)
        captured = send_webhook(client, gateway, captured_body, "event_captured_second")
        failed_last = send_webhook(client, gateway, failed_body, "event_failed_last")
        paid = client.get(f"/api/orders/{order['id']}")

    assert failed_first.status_code == 200
    assert pending.json()["status"] == "payment_pending"
    assert captured.status_code == 200
    assert captured.json()["reason"] == "verified"
    assert failed_last.status_code == 200
    assert paid.json()["status"] == "paid"


def test_provider_order_failure_is_safe_and_not_retried_implicitly(tmp_path: Path) -> None:
    gateway = FakeRazorpayGateway()
    gateway.fail_creation = True
    with make_client(tmp_path, gateway) as client:
        order = create_internal_order(client)
        first = client.post(f"/api/orders/{order['id']}/razorpay-checkout")
        second = client.post(f"/api/orders/{order['id']}/razorpay-checkout")

    assert first.status_code == 503
    assert first.json()["error"] == "RAZORPAY_UNAVAILABLE"
    assert second.status_code == 503
    assert second.json()["error"] == "CHECKOUT_CREATION_FAILED"
    assert gateway.create_count == 1


def test_concurrent_checkout_requests_create_at_most_one_provider_order(tmp_path: Path) -> None:
    gateway = FakeRazorpayGateway()
    with make_client(tmp_path, gateway) as client:
        order = create_internal_order(client)
        barrier = Barrier(2)

        def worker() -> int:
            barrier.wait()
            return client.post(f"/api/orders/{order['id']}/razorpay-checkout").status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(lambda _: worker(), range(2)))

    assert 201 in statuses
    assert set(statuses) <= {201, 409}
    assert gateway.create_count == 1


def test_webhook_rejects_invalid_signature(tmp_path: Path) -> None:
    gateway = FakeRazorpayGateway()
    with make_client(tmp_path, gateway) as client:
        _, checkout = open_checkout(client, gateway)
        raw_body = webhook_payload("payment.captured", checkout, "pay_BadWebhook")
        response = client.post(
            "/api/payments/razorpay/webhook",
            content=raw_body,
            headers={
                "content-type": "application/json",
                "x-razorpay-event-id": "event_bad_signature",
                "x-razorpay-signature": "0" * 64,
            },
        )

    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_WEBHOOK_SIGNATURE"


def test_live_credentials_are_refused(monkeypatch) -> None:
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_live_not_allowed")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "webhook")

    with pytest.raises(RazorpayError) as caught:
        RazorpaySettings.from_env()

    assert caught.value.code == "RAZORPAY_TEST_MODE_REQUIRED"


def test_checkout_fails_honestly_without_credentials(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)
    monkeypatch.delenv("RAZORPAY_WEBHOOK_SECRET", raising=False)
    app = create_app(f"sqlite:///{tmp_path / 'unconfigured.db'}")
    with TestClient(app) as client:
        order = create_internal_order(client)
        response = client.post(f"/api/orders/{order['id']}/razorpay-checkout")

    assert response.status_code == 503
    assert response.json()["error"] == "RAZORPAY_NOT_CONFIGURED"
