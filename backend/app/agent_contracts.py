import hashlib
import json
import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Product
from .policy import load_policy

COMPLEMENT_CATEGORIES = {
    "Kurti, Saree & Lehenga": ("Jewellery & Accessories", "Bags & Footwear"),
    "Women Western": ("Jewellery & Accessories", "Bags & Footwear"),
    "Men": ("Bags & Footwear",),
    "Kids & Toys": ("Bags & Footwear",),
    "Beauty & Health": ("Jewellery & Accessories",),
    "Lingerie": ("Women Western",),
    "Jewellery & Accessories": ("Kurti, Saree & Lehenga", "Women Western"),
    "Bags & Footwear": ("Women Western", "Men"),
    "Home & Kitchen": ("Popular",),
    "Popular": ("Jewellery & Accessories", "Bags & Footwear"),
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _product_number(product_id: str) -> int:
    digits = "".join(character for character in product_id if character.isdigit())
    return int(digits or "0")


def _compatibility_tags(product: Product) -> list[str]:
    values = {
        f"category:{slug(product.category)}",
        f"audience:{slug(product.audience)}",
        f"occasion:{slug(product.occasion)}",
        f"material:{slug(product.material)}",
    }
    for key, value in product.specs.items():
        if isinstance(value, str) and len(value) <= 80:
            values.add(f"{slug(key)}:{slug(value)}")
    return sorted(value for value in values if not value.endswith(":"))


def _complements(product: Product, by_category: dict[str, list[Product]]) -> list[str]:
    result: list[str] = []
    offset = _product_number(product.id)
    for category in COMPLEMENT_CATEGORIES.get(product.category, ()):
        candidates = by_category.get(category, [])
        if candidates:
            result.append(candidates[offset % len(candidates)].id)
    return result


def build_agent_catalog(session: Session) -> dict[str, object]:
    products = list(session.scalars(select(Product).order_by(Product.id)))
    by_category: dict[str, list[Product]] = defaultdict(list)
    for product in products:
        by_category[product.category].append(product)

    version_material = [
        [product.id, product.version, product.price_paise, product.stock] for product in products
    ]
    version_hash = hashlib.sha256(
        json.dumps(version_material, separators=(",", ":")).encode()
    ).hexdigest()[:12]

    return {
        "schema_version": "1.0",
        "catalog_version": f"2026-08-22.1+{version_hash}",
        "merchant": {
            "id": "niyamcart-demo",
            "name": "NiyamCart",
            "currency": "INR",
            "human_approval_required": True,
        },
        "products": [
            {
                "product_id": product.id,
                "version": product.version,
                "name": product.name,
                "brand": product.brand,
                "category": product.category,
                "description": product.description,
                "price": {"amount_paise": product.price_paise, "currency": "INR"},
                "original_price": {
                    "amount_paise": product.original_price_paise,
                    "currency": "INR",
                },
                "availability": {
                    "in_stock": product.stock > 0,
                    "quantity": product.stock,
                    "delivery_days": product.delivery_days,
                },
                "attributes": {
                    "audience": product.audience,
                    "occasion": product.occasion,
                    "material": product.material,
                    "rating": product.rating,
                    "review_count": product.reviews,
                    "free_delivery": product.free_delivery,
                    "return_window_days": product.return_window_days,
                    "highlights": product.highlights,
                    "badges": product.badges,
                    "specs": product.specs,
                },
                "compatibility": {
                    "tags": _compatibility_tags(product),
                    "complements": _complements(product, by_category),
                },
                "policy_refs": [
                    "POL-DENY-LINE-QUANTITY",
                    "POL-ESCALATE-HIGH-VALUE",
                ],
                "image": product.image,
            }
            for product in products
        ],
    }


def build_agent_policy() -> dict[str, object]:
    return load_policy()


def payload_etag(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f'"{hashlib.sha256(encoded).hexdigest()}"'
