from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Product

COLOR_WORDS = {
    "berry",
    "black",
    "blue",
    "cream",
    "emerald",
    "indigo",
    "ivory",
    "maroon",
    "rose",
    "saffron",
    "white",
}

COMPLEMENT_CATEGORIES = {
    "Kurti, Saree & Lehenga": ("Jewellery & Accessories", "Bags & Footwear"),
    "Women Western": ("Jewellery & Accessories", "Bags & Footwear"),
    "Men": ("Bags & Footwear",),
    "Kids & Toys": ("Bags & Footwear",),
    "Beauty & Health": ("Jewellery & Accessories",),
    "Lingerie": ("Women Western",),
    "Jewellery & Accessories": ("Kurti, Saree & Lehenga", "Women Western"),
    "Bags & Footwear": ("Women Western", "Men"),
    "Home & Kitchen": ("Home & Kitchen",),
    "Popular": ("Jewellery & Accessories", "Bags & Footwear"),
}


def product_number(product_id: str) -> int:
    digits = "".join(character for character in product_id if character.isdigit())
    return int(digits or "0")


def _colour(product: Product) -> str | None:
    return next((word for word in product.name.lower().split() if word in COLOR_WORDS), None)


def compatibility_evidence(primary: Product, addon: Product) -> tuple[int, list[str]]:
    score = 45
    evidence = [f"Merchant rule pairs {primary.category} with {addon.category}."]
    primary_type = str(primary.specs.get("product_type", ""))
    addon_type = str(addon.specs.get("product_type", ""))
    if primary.category == "Home & Kitchen":
        score = 60
        evidence = [f"{addon_type} is the mapped complement for {primary_type}."]
    if _colour(primary) and _colour(primary) == _colour(addon):
        score += 15
        evidence.append(f"Both catalogue items use the {_colour(primary)} colour family.")
    elif _colour(primary) and _colour(addon):
        score += 10
        evidence.append(
            f"{_colour(addon).title()} is a merchant-approved pairing with "
            f"{_colour(primary)}."
        )
    if primary.occasion.lower() == addon.occasion.lower():
        score += 15
        evidence.append(f"Both are tagged for {primary.occasion.lower()} use.")
    elif primary.category == "Home & Kitchen":
        score += 10
        evidence.append("The pairing stays within the same home-use context.")
    rating_points = round(addon.rating / 5 * 15)
    score += rating_points
    evidence.append(f"Add-on rating contributes {rating_points}/15 ({addon.rating:.1f}/5).")
    if addon.free_delivery:
        score += 10
        evidence.append(f"Free delivery in {addon.delivery_days}–{addon.delivery_days + 2} days.")
    elif addon.stock > 0:
        score += 5
        evidence.append(
            f"In stock with delivery in {addon.delivery_days}–"
            f"{addon.delivery_days + 2} days."
        )
    return min(100, score), evidence


def products_by_category(products: list[Product]) -> dict[str, list[Product]]:
    result: dict[str, list[Product]] = defaultdict(list)
    for product in products:
        result[product.category].append(product)
    return result


def complement_product_ids(product: Product, by_category: dict[str, list[Product]]) -> list[str]:
    if product.category == "Home & Kitchen":
        product_type = str(product.specs.get("product_type", "")).lower()
        preferred_type = (
            "cotton cushion cover pack"
            if "bedsheet" in product_type or "lamp" in product_type
            else "microfibre door mat set"
            if "towel" in product_type
            else "kitchen organizer rack"
            if any(term in product_type for term in ("cookware", "fry pan", "storage jar"))
            else "airtight storage jar set"
        )
        candidates = [
            candidate
            for candidate in by_category.get("Home & Kitchen", [])
            if candidate.id != product.id
            and str(candidate.specs.get("product_type", "")).lower() == preferred_type
        ]
        if candidates:
            candidates.sort(
                key=lambda candidate: (
                    -compatibility_evidence(product, candidate)[0],
                    abs(candidate.price_paise - product.price_paise),
                    candidate.id,
                )
            )
            return [candidate.id for candidate in candidates[:3]]
    result: list[str] = []
    offset = product_number(product.id)
    for category in COMPLEMENT_CATEGORIES.get(product.category, ()):
        candidates = by_category.get(category, [])
        candidates = [candidate for candidate in candidates if candidate.id != product.id]
        candidates.sort(
            key=lambda candidate: (
                -compatibility_evidence(product, candidate)[0],
                abs(candidate.price_paise - product.price_paise),
                (product_number(candidate.id) - offset) % max(1, len(candidates)),
            )
        )
        result.extend(candidate.id for candidate in candidates[:2])
    return result


def compatible_addon_ids(session: Session, product: Product) -> list[str]:
    products = list(session.scalars(select(Product).order_by(Product.id)))
    return complement_product_ids(product, products_by_category(products))
