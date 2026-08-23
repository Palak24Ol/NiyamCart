import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Product

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "catalog.json"


def load_catalog() -> list[dict[str, object]]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or len(payload) != 500:
        raise ValueError("NiyamCart catalogue must contain exactly 500 products")
    return payload


def seed_catalog(session: Session) -> None:
    items = load_catalog()
    existing = {product.id: product for product in session.scalars(select(Product))}
    for item in items:
        product_id = str(item["id"])
        product = existing.get(product_id)
        if product is None:
            product = Product(id=product_id)
            session.add(product)
        elif product.version >= int(item["version"]):
            continue
        product.name = str(item["name"])
        product.brand = str(item["brand"])
        product.category = str(item["category"])
        product.audience = str(item["audience"])
        product.description = str(item["description"])
        product.price_paise = int(item["pricePaise"])
        product.original_price_paise = int(item["originalPricePaise"])
        product.rating = float(item["rating"])
        product.reviews = int(item["reviews"])
        product.stock = int(item["stock"])
        product.delivery_days = int(item["deliveryDays"])
        product.free_delivery = bool(item["freeDelivery"])
        product.occasion = str(item["occasion"])
        product.material = str(item["material"])
        product.highlights = list(item["highlights"])
        product.badges = list(item["badges"])
        product.specs = dict(item["specs"])
        product.size_chart = item["sizeChart"]
        product.return_window_days = int(item["returnWindowDays"])
        product.image = str(item["image"])
        product.version = int(item["version"])
    session.commit()
