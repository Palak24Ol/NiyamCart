from pathlib import Path

from app.main import create_app
from fastapi.testclient import TestClient


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}")
    return TestClient(app)


def test_health(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "niyamcart-api"}


def test_catalog_uses_integer_paise(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/api/products")

    payload = response.json()
    assert response.status_code == 200
    assert payload["count"] == 500
    assert all(isinstance(item["price_paise"], int) for item in payload["items"])


def test_catalog_filter_and_product_not_found(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        filtered = client.get("/api/products", params={"category": "Men"})
        missing = client.get("/api/products/does-not-exist")

    assert filtered.status_code == 200
    assert filtered.json()["count"] == 50
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Product not found"
