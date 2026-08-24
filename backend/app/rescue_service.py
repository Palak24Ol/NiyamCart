from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import append_audit
from .auth_models import Customer
from .commerce import CommerceError, create_cart, load_cart
from .commerce_schemas import CartItemInput, CreateCartRequest
from .fulfillment_service import confirm_cart_delivery
from .models import Product
from .offer_service import select_offer
from .rescue_schemas import RescueCartRequest, RescueCartResponse, RescueItemDiff


def rescue_cart(
    db: Session,
    customer: Customer,
    cart_id: str,
    payload: RescueCartRequest,
) -> RescueCartResponse:
    old = load_cart(db, cart_id)
    if old.fulfillment is None or old.fulfillment.customer_id != customer.id:
        raise CommerceError(403, "CART_NOT_OWNED", "This checkout cart belongs to another user")
    unavailable = set(payload.unavailable_product_ids)
    if payload.simulate_inventory_change and not unavailable and old.items:
        unavailable.add(old.items[0].product_id)
    if not unavailable:
        raise CommerceError(422, "NO_CART_FAILURE", "Choose a failed item to demonstrate rescue")

    all_products = list(db.scalars(select(Product).where(Product.stock > 0).order_by(Product.id)))
    products = {product.id: product for product in all_products}
    new_items: list[CartItemInput] = []
    changes: list[RescueItemDiff] = []
    for item in old.items:
        current = products.get(item.product_id)
        failed = item.product_id in unavailable or current is None or current.stock < item.quantity
        if not failed:
            new_items.append(CartItemInput(product_id=item.product_id, quantity=item.quantity))
            continue
        original = current or db.get(Product, item.product_id)
        if original is None:
            raise CommerceError(
                409, "RESCUE_UNAVAILABLE", "The original product is no longer known"
            )
        candidates = [
            product
            for product in all_products
            if product.id not in unavailable
            and product.id != item.product_id
            and product.category == original.category
            and product.stock >= item.quantity
            and product.price_paise <= item.unit_price_paise + 10000
        ]
        candidates.sort(
            key=lambda product: (
                abs(product.price_paise - item.unit_price_paise),
                -product.rating,
                product.id,
            )
        )
        if not candidates:
            raise CommerceError(
                409,
                "NO_SAFE_REPLACEMENT",
                "No in-stock replacement preserves the category and price boundary",
            )
        replacement = candidates[0]
        new_items.append(CartItemInput(product_id=replacement.id, quantity=item.quantity))
        changes.append(
            RescueItemDiff(
                old_product_id=item.product_id,
                old_product_name=item.product_name,
                old_price_paise=item.unit_price_paise,
                new_product_id=replacement.id,
                new_product_name=replacement.name,
                new_price_paise=replacement.price_paise,
                reason="Same category, in stock, nearest price within the ₹100 rescue boundary.",
            )
        )

    replacement_cart = create_cart(db, CreateCartRequest(items=new_items))
    confirm_cart_delivery(
        db,
        customer,
        replacement_cart.id,
        old.fulfillment.address_id,
        confirmed=True,
    )
    select_offer(db, customer, replacement_cart.id, "standard", confirmed=True)
    old.status = "invalidated"
    append_audit(
        db,
        "cart",
        old.id,
        "cart_rescued",
        {
            "replacement_cart_id": replacement_cart.id,
            "previous_approval_revoked": True,
            "requires_new_review_and_approval": True,
            "simulated_inventory_change": payload.simulate_inventory_change,
            "changes": [change.model_dump() for change in changes],
        },
    )
    db.commit()
    refreshed = load_cart(db, replacement_cart.id)
    return RescueCartResponse(
        previous_cart_id=old.id,
        replacement_cart_id=refreshed.id,
        previous_approval_revoked=True,
        intent_preserved=True,
        price_delta_paise=refreshed.subtotal_paise - old.subtotal_paise,
        data_mode="simulated_test" if payload.simulate_inventory_change else "live_validation",
        changes=changes,
    )
