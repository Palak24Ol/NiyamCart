import hashlib
import random
from pathlib import Path

from app.catalog import seed_catalog
from app.commerce import canonical_cart, create_cart, freeze_cart
from app.commerce_schemas import CartItemInput, CreateCartRequest
from app.database import Database
from app.models import Product
from sqlalchemy import select


def test_randomized_cart_totals_and_hashes_preserve_money_invariants(tmp_path: Path) -> None:
    randomizer = random.Random(240822)
    database = Database(f"sqlite:///{tmp_path / 'properties.db'}")
    database.create_schema()
    with database.session_factory() as session:
        seed_catalog(session)
        products = list(session.scalars(select(Product).order_by(Product.id)))
        authoritative_prices = {product.id: product.price_paise for product in products}

        for _ in range(30):
            selected = randomizer.sample(products, randomizer.randint(1, 5))
            quantities = {product.id: randomizer.randint(1, 10) for product in selected}
            cart = create_cart(
                session,
                CreateCartRequest(
                    items=[
                        CartItemInput(product_id=product.id, quantity=quantities[product.id])
                        for product in selected
                    ]
                ),
            )
            expected_total = sum(
                authoritative_prices[product.id] * quantities[product.id]
                for product in selected
            )
            assert cart.total_paise == expected_total
            assert all(isinstance(item.line_total_paise, int) for item in cart.items)

            frozen = freeze_cart(session, cart.id)
            assert frozen.cart_hash == hashlib.sha256(canonical_cart(frozen)).hexdigest()
            assert len(frozen.cart_hash) == 64

    database.close()
