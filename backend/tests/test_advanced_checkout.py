from pathlib import Path

from app.main import create_app
from fastapi.testclient import TestClient


def signup(client: TestClient) -> None:
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "Demo Shopper",
            "email": "advanced@example.com",
            "password": "SafePass123",
        },
    )
    assert response.status_code == 201


def proposed_cart(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/carts", json={"items": [{"product_id": "P-001", "quantity": 1}]}
    )
    assert response.status_code == 201
    return response.json()


def address(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/customer/addresses",
        json={
            "label": "Home",
            "recipient_name": "Demo Shopper",
            "phone": "+919876543210",
            "line1": "42 Test House",
            "locality": "Indiranagar",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560038",
            "is_default": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_final_checkout_requires_confirmed_delivery_and_offer(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'advanced.db'}")
    with TestClient(app) as client:
        signup(client)
        cart = proposed_cart(client)
        missing_delivery = client.post(f"/api/carts/{cart['id']}/finalize")
        saved = address(client)
        quote = client.post(
            f"/api/carts/{cart['id']}/delivery",
            json={"address_id": saved["id"], "confirmed": True},
        )
        missing_offer = client.post(f"/api/carts/{cart['id']}/finalize")
        selected = client.post(
            f"/api/carts/{cart['id']}/payment-offer",
            json={"offer_key": "standard", "confirmed": True},
        )
        frozen = client.post(f"/api/carts/{cart['id']}/finalize")
        audit = client.get(f"/api/audit/cart/{cart['id']}")

    assert missing_delivery.status_code == 409
    assert missing_delivery.json()["error"] == "DELIVERY_REQUIRED"
    assert quote.status_code == 200
    assert quote.json()["masked_pincode"] == "560***"
    assert missing_offer.status_code == 409
    assert missing_offer.json()["error"] == "PAYMENT_OFFER_REQUIRED"
    assert selected.status_code == 200
    assert frozen.status_code == 200
    assert frozen.json()["cart_hash"]
    audit_text = str(audit.json())
    assert "42 Test House" not in audit_text
    assert "560***" in audit_text


def test_unconfigured_offers_are_preview_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("RAZORPAY_OFFER_UPI_ID", raising=False)
    app = create_app(f"sqlite:///{tmp_path / 'offers.db'}")
    with TestClient(app) as client:
        signup(client)
        cart = proposed_cart(client)
        saved = address(client)
        client.post(
            f"/api/carts/{cart['id']}/delivery",
            json={"address_id": saved["id"], "confirmed": True},
        )
        offers = client.get(f"/api/carts/{cart['id']}/payment-offers")
        card = next(item for item in offers.json()["items"] if item["key"] == "upi_saver")
        forced = client.post(
            f"/api/carts/{cart['id']}/payment-offer",
            json={"offer_key": "upi_saver", "confirmed": True},
        )

    assert card["status"] == "preview"
    assert card["provider_configured"] is False
    assert forced.status_code == 409
    assert forced.json()["error"] == "OFFER_NOT_CONFIGURED"


def test_best_merchant_coupon_is_selectable_and_sets_discounted_order_total(
    tmp_path: Path,
) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'merchant-offer.db'}")
    with TestClient(app) as client:
        signup(client)
        cart_response = client.post(
            "/api/carts", json={"items": [{"product_id": "P-001", "quantity": 6}]}
        )
        cart = cart_response.json()
        saved = address(client)
        client.post(
            f"/api/carts/{cart['id']}/delivery",
            json={"address_id": saved["id"], "confirmed": True},
        )
        offers = client.get(f"/api/carts/{cart['id']}/payment-offers").json()
        best = next(item for item in offers["items"] if item["key"] == offers["best_offer_key"])
        selected = client.post(
            f"/api/carts/{cart['id']}/payment-offer",
            json={
                "offer_key": best["key"],
                "preferred_payment_method": "card",
                "confirmed": True,
            },
        )
        frozen = client.post(f"/api/carts/{cart['id']}/finalize").json()
        client.post(
            f"/api/carts/{cart['id']}/approve",
            json={"cart_hash": frozen["cart_hash"]},
        )
        order = client.post(
            "/api/orders",
            json={
                "cart_id": cart["id"],
                "cart_hash": frozen["cart_hash"],
                "idempotency_key": f"merchant-offer-{cart['id']}",
            },
        )

    assert offers["best_offer_key"] == "festive_8"
    assert best["code"] == "FESTIVE8"
    assert best["status"] == "available"
    assert best["savings_paise"] > 0
    assert selected.status_code == 200
    assert selected.json()["payment_method"] == "card"
    assert order.status_code == 201
    assert order.json()["total_paise"] == best["expected_payable_paise"]


def test_cart_rescue_revokes_approval_and_requires_fresh_review(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'rescue.db'}")
    with TestClient(app) as client:
        signup(client)
        cart = proposed_cart(client)
        saved = address(client)
        client.post(
            f"/api/carts/{cart['id']}/delivery",
            json={"address_id": saved["id"], "confirmed": True},
        )
        client.post(
            f"/api/carts/{cart['id']}/payment-offer",
            json={"offer_key": "standard", "confirmed": True},
        )
        frozen = client.post(f"/api/carts/{cart['id']}/finalize").json()
        client.post(
            f"/api/carts/{cart['id']}/approve", json={"cart_hash": frozen["cart_hash"]}
        )
        rescued = client.post(
            f"/api/carts/{cart['id']}/rescue",
            json={"simulate_inventory_change": True},
        )
        assert rescued.status_code == 200, rescued.json()
        old = client.get(f"/api/carts/{cart['id']}")
        replacement = client.get(f"/api/carts/{rescued.json()['replacement_cart_id']}")

    assert rescued.status_code == 200
    assert rescued.json()["previous_approval_revoked"] is True
    assert rescued.json()["requires_new_review_and_approval"] is True
    assert rescued.json()["changes"]
    assert old.json()["status"] == "invalidated"
    assert replacement.json()["status"] == "proposed"


def test_causal_growth_ledger_counts_only_accepted_uplift(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'growth.db'}")
    with TestClient(app) as client:
        base = {
            "primary_product_id": "P-001",
            "addon_product_id": "P-101",
            "baseline_paise": 35900,
            "suggested_paise": 61700,
        }
        client.post("/api/growth/events", json={**base, "event_type": "exposed"})
        client.post("/api/growth/events", json={**base, "event_type": "rejected"})
        client.post("/api/growth/events", json={**base, "event_type": "accepted"})
        ledger = client.get("/api/growth/ledger")

    assert ledger.status_code == 200
    assert ledger.json()["data_mode"] == "test_demo"
    assert ledger.json()["exposures"] == 1
    assert ledger.json()["accepted"] == 1
    assert ledger.json()["rejected"] == 1
    assert ledger.json()["incremental_revenue_paise"] == 25800


def test_reverse_geocoding_requires_explicit_public_provider_consent(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'location.db'}")
    with TestClient(app) as client:
        response = client.post(
            "/api/location/reverse-geocode",
            json={"latitude": 12.9716, "longitude": 77.5946},
        )
    assert response.status_code == 428
    assert response.json()["error"] == "LOCATION_SHARING_CONFIRMATION_REQUIRED"


def test_reverse_geocoding_uses_public_provider_only_after_consent(
    tmp_path: Path, monkeypatch
) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "display_name": "MG Road, Bengaluru, Karnataka, 560001, India",
                "address": {
                    "road": "MG Road",
                    "suburb": "Ashok Nagar",
                    "city": "Bengaluru",
                    "state": "Karnataka",
                    "postcode": "560001",
                    "country_code": "in",
                },
            }

    calls: list[tuple[str, dict[str, object]]] = []

    def fake_get(url: str, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.delenv("REVERSE_GEOCODING_URL", raising=False)
    monkeypatch.setattr("app.fulfillment_service.httpx.get", fake_get)
    app = create_app(f"sqlite:///{tmp_path / 'location-consent.db'}")
    with TestClient(app) as client:
        response = client.post(
            "/api/location/reverse-geocode",
            json={
                "latitude": 12.9716,
                "longitude": 77.5946,
                "allow_public_provider": True,
            },
        )

    assert response.status_code == 200
    assert response.json()["city"] == "Bengaluru"
    assert response.json()["pincode"] == "560001"
    assert calls[0][0] == "https://nominatim.openstreetmap.org/reverse"
    assert calls[0][1]["params"]["lat"] == 12.9716


def test_bedsheet_cross_sell_is_a_scored_home_complement(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'compatibility.db'}")
    with TestClient(app) as client:
        response = client.get("/api/products/P-252/compatible-addons?limit=3")
        product_ids = [item["product_id"] for item in response.json()["items"]]
        products = [client.get(f"/api/products/{product_id}").json() for product_id in product_ids]

    assert response.status_code == 200
    assert len(product_ids) == 3
    assert all(product["category"] == "Home & Kitchen" for product in products)
    assert all("Cushion Cover" in product["name"] for product in products)
    assert all(item["match_score"] >= 80 for item in response.json()["items"])
    assert all(item["evidence"] for item in response.json()["items"])
