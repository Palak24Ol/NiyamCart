from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .audit import append_audit
from .auth_models import Customer
from .auth_service import AuthError
from .commerce import CommerceError, load_cart
from .commerce_models import CartFulfillment, CustomerAddress
from .fulfillment_schemas import AddressInput, ReverseGeocodeRequest, ReverseGeocodeResponse
from .models import Product


def list_addresses(db: Session, customer: Customer) -> list[CustomerAddress]:
    return list(
        db.scalars(
            select(CustomerAddress)
            .where(CustomerAddress.customer_id == customer.id)
            .order_by(CustomerAddress.is_default.desc(), CustomerAddress.created_at.desc())
        )
    )


def save_address(
    db: Session,
    customer: Customer,
    payload: AddressInput,
    address_id: str | None = None,
) -> CustomerAddress:
    address = db.get(CustomerAddress, address_id) if address_id else None
    if address_id and (address is None or address.customer_id != customer.id):
        raise AuthError(404, "ADDRESS_NOT_FOUND", "Delivery address not found")
    if address is None:
        address = CustomerAddress(id=str(uuid4()), customer_id=customer.id)
        db.add(address)
    for key, value in payload.model_dump().items():
        setattr(address, key, value)
    if payload.is_default:
        db.execute(
            update(CustomerAddress)
            .where(
                CustomerAddress.customer_id == customer.id,
                CustomerAddress.id != address.id,
            )
            .values(is_default=False)
        )
    db.commit()
    db.refresh(address)
    return address


def _fingerprint(customer_id: str, address: CustomerAddress) -> str:
    payload = {
        "customer_id": customer_id,
        "address_id": address.id,
        "recipient_name": address.recipient_name,
        "phone": address.phone,
        "line1": address.line1,
        "locality": address.locality,
        "landmark": address.landmark,
        "city": address.city,
        "state": address.state,
        "pincode": address.pincode,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def confirm_cart_delivery(
    db: Session,
    customer: Customer,
    cart_id: str,
    address_id: str,
    confirmed: bool,
) -> CartFulfillment:
    if not confirmed:
        raise CommerceError(422, "ADDRESS_CONFIRMATION_REQUIRED", "Confirm the address first")
    cart = load_cart(db, cart_id)
    if cart.status != "proposed":
        raise CommerceError(
            409,
            "CART_ALREADY_LOCKED",
            "Changing the address requires a new cart review and approval",
        )
    address = db.get(CustomerAddress, address_id)
    if address is None or address.customer_id != customer.id:
        raise AuthError(404, "ADDRESS_NOT_FOUND", "Delivery address not found")
    products = {
        product.id: product
        for product in db.scalars(
            select(Product).where(Product.id.in_([item.product_id for item in cart.items]))
        )
    }
    if len(products) != len(cart.items):
        raise CommerceError(409, "CART_CHANGED", "A cart product is unavailable")
    delivery_paise = (
        0 if all(products[item.product_id].free_delivery for item in cart.items) else 4900
    )
    base_eta = max(products[item.product_id].delivery_days for item in cart.items)
    now = datetime.now(UTC).replace(tzinfo=None)
    fulfillment = db.get(CartFulfillment, cart.id)
    if fulfillment is None:
        fulfillment = CartFulfillment(cart_id=cart.id)
        db.add(fulfillment)
    cart.fulfillment = fulfillment
    for field in (
        "label",
        "recipient_name",
        "phone",
        "line1",
        "locality",
        "landmark",
        "city",
        "state",
        "pincode",
    ):
        setattr(
            fulfillment,
            "address_label" if field == "label" else field,
            getattr(address, field),
        )
    fulfillment.customer_id = customer.id
    fulfillment.address_id = address.id
    fulfillment.address_fingerprint = _fingerprint(customer.id, address)
    fulfillment.delivery_paise = delivery_paise
    fulfillment.eta_min_days = max(1, base_eta)
    fulfillment.eta_max_days = base_eta + 2
    fulfillment.confirmed_at = now
    cart.total_paise = cart.subtotal_paise + delivery_paise
    append_audit(
        db,
        "cart",
        cart.id,
        "delivery_address_confirmed",
        {
            "address_summary": f"{address.city} · {address.pincode[:3]}***",
            "delivery_paise": delivery_paise,
            "eta_min_days": fulfillment.eta_min_days,
            "eta_max_days": fulfillment.eta_max_days,
            "full_address_shared_with_agent": False,
        },
    )
    db.commit()
    db.refresh(fulfillment)
    return fulfillment


def reverse_geocode(payload: ReverseGeocodeRequest) -> ReverseGeocodeResponse:
    base_url = os.getenv("REVERSE_GEOCODING_URL", "").strip()
    if not base_url:
        if not payload.allow_public_provider:
            raise CommerceError(
                428,
                "LOCATION_SHARING_CONFIRMATION_REQUIRED",
                "Confirm before sharing precise coordinates with OpenStreetMap.",
            )
        base_url = "https://nominatim.openstreetmap.org/reverse"
    try:
        response = httpx.get(
            base_url,
            params={
                "lat": payload.latitude,
                "lon": payload.longitude,
                "format": "jsonv2",
                "addressdetails": 1,
                "zoom": 18,
                "layer": "address",
            },
            headers={
                "User-Agent": os.getenv("REVERSE_GEOCODING_USER_AGENT", "NiyamCart-Buildathon/0.1")
            },
            timeout=8.0,
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise CommerceError(
            503,
            "REVERSE_GEOCODING_UNAVAILABLE",
            "Location was detected, but address lookup failed. Enter the address manually.",
        ) from error
    address = body.get("address", {}) if isinstance(body, dict) else {}
    if not isinstance(address, dict):
        address = {}
    country_code = str(address.get("country_code", "")).lower()
    if country_code and country_code != "in":
        raise CommerceError(422, "INDIA_DELIVERY_ONLY", "This demo currently delivers in India")
    city = str(
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("county")
        or ""
    )
    state = str(address.get("state") or "")
    pincode = "".join(
        character for character in str(address.get("postcode") or "") if character.isdigit()
    )[:6]
    locality = str(address.get("suburb") or address.get("neighbourhood") or city)
    road = str(address.get("road") or address.get("pedestrian") or locality)
    house = str(address.get("house_number") or "")
    line1 = ", ".join(value for value in (house, road) if value)
    if not city or not state or len(pincode) != 6:
        raise CommerceError(
            422,
            "INCOMPLETE_LOCATION_ADDRESS",
            "Location was found, but the house address or Indian pincode needs confirmation.",
        )
    return ReverseGeocodeResponse(
        display_name=str(body.get("display_name") or ", ".join([line1, locality, city])),
        line1=line1 or locality,
        locality=locality,
        city=city,
        state=state,
        pincode=pincode,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
