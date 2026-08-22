import json
from pathlib import Path

import pytest
import yaml
from app.main import create_app
from app.models import Product
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
CATALOG_SCHEMA = ROOT / "backend" / "schemas" / "agent-catalog.schema.json"
POLICY_SCHEMA = ROOT / "backend" / "schemas" / "agent-policy.schema.json"


def make_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{tmp_path / 'contracts.db'}"))


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_catalog_contract_contains_500_schema_valid_products(tmp_path: Path) -> None:
    schema = load_json(CATALOG_SCHEMA)
    Draft202012Validator.check_schema(schema)

    with make_client(tmp_path) as client:
        response = client.get("/.well-known/agent-catalog.json")

    assert response.status_code == 200
    payload = response.json()
    Draft202012Validator(schema).validate(payload)
    assert len(payload["products"]) == 500
    assert all(isinstance(item["price"]["amount_paise"], int) for item in payload["products"])
    assert payload["merchant"]["human_approval_required"] is True


def test_compatibility_references_are_grounded(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        products = client.get("/.well-known/agent-catalog.json").json()["products"]

    product_ids = {product["product_id"] for product in products}
    assert all(product["compatibility"]["tags"] for product in products)
    assert all(
        complement in product_ids
        for product in products
        for complement in product["compatibility"]["complements"]
    )
    assert any(product["compatibility"]["complements"] for product in products)


def test_catalog_etag_supports_cache_and_changes_with_inventory(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'etag.db'}")
    with TestClient(app) as client:
        first = client.get("/.well-known/agent-catalog.json")
        first_etag = first.headers["etag"]
        cached = client.get(
            "/.well-known/agent-catalog.json",
            headers={"If-None-Match": first_etag},
        )

        with app.state.db.session_factory() as session:
            product = session.get(Product, "P-001")
            assert product is not None
            product.stock -= 1
            session.commit()

        changed = client.get("/.well-known/agent-catalog.json")

    assert cached.status_code == 304
    assert changed.headers["etag"] != first_etag
    assert changed.json()["catalog_version"] != first.json()["catalog_version"]


def test_policy_contract_is_schema_valid_and_cacheable(tmp_path: Path) -> None:
    schema = load_json(POLICY_SCHEMA)
    Draft202012Validator.check_schema(schema)

    with make_client(tmp_path) as client:
        response = client.get("/.well-known/agent-policy.json")
        cached = client.get(
            "/.well-known/agent-policy.json",
            headers={"If-None-Match": response.headers["etag"]},
        )

    assert response.status_code == 200
    Draft202012Validator(schema).validate(response.json())
    assert cached.status_code == 304
    assert len(response.json()["rules"]) == 7


@pytest.mark.parametrize(
    ("evaluation_input", "decision", "rule_id"),
    [
        ({"action": "recommend", "total_paise": 100_000}, "allow", "POL-ALLOW-BOUNDED-COMMERCE"),
        ({"action": "create_payment"}, "deny", "POL-DENY-AUTONOMOUS-PAYMENT"),
        ({"action": "recommend", "currency": "USD"}, "deny", "POL-DENY-CURRENCY"),
        ({"action": "propose_cart", "max_line_quantity": 11}, "deny", "POL-DENY-LINE-QUANTITY"),
        ({"action": "propose_cart", "line_count": 21}, "deny", "POL-DENY-CART-SIZE"),
        ({"action": "checkout", "total_paise": 500_001}, "escalate", "POL-ESCALATE-HIGH-VALUE"),
        ({"action": "return_item"}, "escalate", "POL-ESCALATE-UNKNOWN-ACTION"),
    ],
)
def test_policy_engine_returns_explainable_decisions(
    tmp_path: Path,
    evaluation_input: dict[str, object],
    decision: str,
    rule_id: str,
) -> None:
    with make_client(tmp_path) as client:
        response = client.post("/api/policy/evaluate", json=evaluation_input)

    assert response.status_code == 200
    assert response.json()["decision"] == decision
    assert response.json()["rule_id"] == rule_id
    assert response.json()["explanation"]


def test_merchant_manifest_points_to_public_contracts() -> None:
    manifest = yaml.safe_load((ROOT / "merchant.yaml").read_text(encoding="utf-8"))

    assert manifest["merchant"]["name"] == "NiyamCart"
    assert manifest["commerce"]["catalog_url"] == "/.well-known/agent-catalog.json"
    assert manifest["commerce"]["policy_url"] == "/.well-known/agent-policy.json"
    assert manifest["payment"]["mode"] == "test"
    assert manifest["payment"]["agent_can_create_payment"] is False
    assert set(manifest["agent"]["supported_actions"]) == {
        "search_catalog",
        "get_product_details",
        "find_compatible_addons",
        "get_policy",
        "propose_cart",
        "escalate_to_human",
    }
