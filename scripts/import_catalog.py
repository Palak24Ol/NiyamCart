"""Normalize the authorized legacy demo catalogue for NiyamCart.

Only product records and primary images are imported. Personal, order, seller,
review, address, and multi-angle catalogue data are deliberately excluded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--products", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output-data", type=Path, required=True)
    parser.add_argument("--output-assets", type=Path, required=True)
    return parser.parse_args()


def require_integer(value: Any, field: str, product_id: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{product_id}: {field} must be an integer")
    return value


def normalize(record: dict[str, Any]) -> dict[str, Any]:
    product_id = str(record["id"])
    price_rupees = require_integer(record["price"], "price", product_id)
    original_rupees = require_integer(record["original_price"], "original_price", product_id)
    stock = require_integer(record["stock"], "stock", product_id)
    if min(price_rupees, original_rupees, stock) < 0:
        raise ValueError(f"{product_id}: negative commerce value")

    description = str(record["description"]).replace(
        "agent-protected purchase", "informed purchase"
    )
    badges = [
        "Catalogue verified" if badge == "Agent verified" else str(badge)
        for badge in record.get("badges", [])
    ]
    brand = str(record.get("brand", "Independent"))
    if brand == "Ghar Saathi":
        brand = "GharMitra"

    return {
        "id": product_id,
        "name": str(record["name"]),
        "brand": brand,
        "category": str(record["category"]),
        "audience": str(record.get("audience", "All")),
        "description": description,
        "pricePaise": price_rupees * 100,
        "originalPricePaise": original_rupees * 100,
        "rating": float(record.get("rating", 0)),
        "reviews": require_integer(record.get("review_count", 0), "review_count", product_id),
        "stock": stock,
        "deliveryDays": require_integer(
            record.get("delivery_days", 0), "delivery_days", product_id
        ),
        "freeDelivery": bool(record.get("free_delivery", False)),
        "occasion": str(record.get("occasion", "")),
        "material": str(record.get("material", "")),
        "highlights": [str(value) for value in record.get("highlights", [])],
        "badges": badges,
        "specs": record.get("specs", {}),
        "sizeChart": record.get("size_chart"),
        "returnWindowDays": require_integer(
            record.get("return_window_days", 0), "return_window_days", product_id
        ),
        "image": f"/catalog/{product_id}.webp",
        "version": 1,
    }


def convert_image(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        converted = image.convert("RGB")
        converted.thumbnail((720, 720), Image.Resampling.LANCZOS)
        converted.save(destination, "WEBP", quality=82, method=6)


def main() -> None:
    args = parse_args()
    raw = json.loads(args.products.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or len(raw) != 500:
        raise ValueError("Expected exactly 500 source products")

    products = [normalize(record) for record in raw]
    ids = [product["id"] for product in products]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate product IDs found")

    args.output_data.parent.mkdir(parents=True, exist_ok=True)
    args.output_assets.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(products, ensure_ascii=False, indent=2) + "\n"
    args.output_data.write_text(payload, encoding="utf-8")

    for product in products:
        source = args.assets / f"{product['id']}.png"
        if not source.is_file():
            raise FileNotFoundError(source)
        convert_image(source, args.output_assets / f"{product['id']}.webp")

    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    categories = sorted({product["category"] for product in products})
    print(json.dumps({"count": len(products), "categories": len(categories), "sha256": digest}))


if __name__ == "__main__":
    main()
