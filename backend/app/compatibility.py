from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Product

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


def product_number(product_id: str) -> int:
    digits = "".join(character for character in product_id if character.isdigit())
    return int(digits or "0")


def products_by_category(products: list[Product]) -> dict[str, list[Product]]:
    result: dict[str, list[Product]] = defaultdict(list)
    for product in products:
        result[product.category].append(product)
    return result


def complement_product_ids(product: Product, by_category: dict[str, list[Product]]) -> list[str]:
    result: list[str] = []
    offset = product_number(product.id)
    for category in COMPLEMENT_CATEGORIES.get(product.category, ()):
        candidates = by_category.get(category, [])
        if candidates:
            result.append(candidates[offset % len(candidates)].id)
    return result


def compatible_addon_ids(session: Session, product: Product) -> list[str]:
    products = list(session.scalars(select(Product).order_by(Product.id)))
    return complement_product_ids(product, products_by_category(products))
