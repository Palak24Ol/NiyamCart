from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from .audit import append_audit
from .auth_models import Customer
from .commerce import CommerceError, load_cart
from .commerce_models import CartOfferSelection
from .offer_schemas import PaymentOfferResponse

OFFER_PATH = Path(__file__).resolve().parents[1] / "data" / "payment_offers.json"


@dataclass(frozen=True)
class OfferDefinition:
    key: str
    title: str
    payment_method: str
    discount_type: str
    discount_value: int
    max_discount_paise: int
    minimum_cart_paise: int
    provider_offer_env: str | None
    funding: str
    terms: str


def _definitions() -> list[OfferDefinition]:
    payload = json.loads(OFFER_PATH.read_text(encoding="utf-8"))
    return [OfferDefinition(**item) for item in payload]


def _provider_id(definition: OfferDefinition) -> str | None:
    if definition.provider_offer_env is None:
        return None
    value = os.getenv(definition.provider_offer_env, "").strip()
    return value if re.fullmatch(r"offer_[A-Za-z0-9]+", value) else None


def _saving(definition: OfferDefinition, total_paise: int) -> int:
    if total_paise < definition.minimum_cart_paise:
        return 0
    if definition.discount_type == "flat":
        return min(definition.discount_value, definition.max_discount_paise, total_paise)
    if definition.discount_type == "percent":
        calculated = round(total_paise * definition.discount_value / 100)
        return min(calculated, definition.max_discount_paise, total_paise)
    return 0


def available_offers(total_paise: int) -> list[PaymentOfferResponse]:
    offers = []
    for definition in _definitions():
        standard = definition.key == "standard"
        eligible = standard or total_paise >= definition.minimum_cart_paise
        provider_configured = (
            standard
            or definition.funding == "merchant"
            or _provider_id(definition) is not None
        )
        savings = _saving(definition, total_paise)
        status = (
            "standard"
            if standard
            else "ineligible"
            if not eligible
            else "available"
            if provider_configured
            else "preview"
        )
        if standard:
            reason = "Always available; you choose the method inside Razorpay."
        elif not eligible:
            reason = f"Requires a cart of at least ₹{definition.minimum_cart_paise / 100:,.0f}."
        elif not provider_configured:
            reason = "Preview only until its Razorpay test Offer ID is configured."
        elif definition.funding == "merchant":
            reason = "Merchant-funded cart coupon; applied before Razorpay test checkout."
        else:
            reason = "Merchant-approved and eligible by cart value; Razorpay checks the instrument."
        offers.append(
            PaymentOfferResponse(
                key=definition.key,
                title=definition.title,
                payment_method=definition.payment_method,
                terms=definition.terms,
                savings_paise=savings,
                expected_payable_paise=total_paise - savings,
                eligible=eligible,
                provider_configured=provider_configured,
                status=status,
                reason=reason,
            )
        )
    return offers


def select_offer(
    db: Session,
    customer: Customer,
    cart_id: str,
    offer_key: str,
    confirmed: bool,
    preferred_payment_method: str = "any",
) -> CartOfferSelection:
    if not confirmed:
        raise CommerceError(422, "OFFER_CONFIRMATION_REQUIRED", "Confirm the payment offer first")
    cart = load_cart(db, cart_id)
    if cart.status != "proposed":
        raise CommerceError(409, "CART_ALREADY_LOCKED", "Offers cannot change after cart locking")
    if cart.fulfillment is None:
        raise CommerceError(409, "DELIVERY_REQUIRED", "Confirm a delivery address first")
    if cart.fulfillment.customer_id != customer.id:
        raise CommerceError(403, "CART_NOT_OWNED", "This checkout cart belongs to another user")
    offer = next(
        (item for item in available_offers(cart.total_paise) if item.key == offer_key), None
    )
    if offer is None:
        raise CommerceError(404, "OFFER_NOT_FOUND", "Payment offer not found")
    if not offer.eligible:
        raise CommerceError(409, "OFFER_NOT_ELIGIBLE", offer.reason)
    if not offer.provider_configured:
        raise CommerceError(409, "OFFER_NOT_CONFIGURED", offer.reason)
    definition = next(item for item in _definitions() if item.key == offer_key)
    selection = db.get(CartOfferSelection, cart.id)
    if selection is None:
        selection = CartOfferSelection(cart_id=cart.id)
        db.add(selection)
    cart.offer_selection = selection
    selection.offer_key = offer.key
    selection.provider_offer_id = _provider_id(definition)
    selection.payment_method = (
        offer.payment_method
        if definition.funding == "razorpay"
        else preferred_payment_method
    )
    selection.title = offer.title
    selection.savings_paise = offer.savings_paise
    selection.expected_payable_paise = offer.expected_payable_paise
    selection.selected_at = datetime.now(UTC).replace(tzinfo=None)
    append_audit(
        db,
        "cart",
        cart.id,
        "payment_offer_selected",
        {
            "offer_key": selection.offer_key,
            "payment_method": selection.payment_method,
            "funding": definition.funding,
            "savings_paise": selection.savings_paise,
            "expected_payable_paise": selection.expected_payable_paise,
            "provider_eligibility_requires_checkout_validation": definition.funding == "razorpay",
            "buyer_confirmed": True,
        },
    )
    db.commit()
    db.refresh(selection)
    return selection
