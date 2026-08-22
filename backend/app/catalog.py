import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Product

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "catalog.json"


def load_catalog() -> list[dict[str, object]]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or len(payload) != 500:
        raise ValueError("NiyamCart catalogue must contain exactly 500 products")
    return payload


def seed_catalog(session: Session) -> None:
    if session.scalar(select(func.count()).select_from(Product)):
        return
    session.add_all(
        Product(
            id=str(item["id"]),
            name=str(item["name"]),
            brand=str(item["brand"]),
            category=str(item["category"]),
            audience=str(item["audience"]),
            description=str(item["description"]),
            price_paise=int(item["pricePaise"]),
            original_price_paise=int(item["originalPricePaise"]),
            rating=float(item["rating"]),
            reviews=int(item["reviews"]),
            stock=int(item["stock"]),
            delivery_days=int(item["deliveryDays"]),
            free_delivery=bool(item["freeDelivery"]),
            occasion=str(item["occasion"]),
            material=str(item["material"]),
            highlights=list(item["highlights"]),
            badges=list(item["badges"]),
            specs=dict(item["specs"]),
            size_chart=item["sizeChart"],
            return_window_days=int(item["returnWindowDays"]),
            image=str(item["image"]),
            version=int(item["version"]),
        )
        for item in load_catalog()
    )
    session.commit()
