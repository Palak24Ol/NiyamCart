from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CartItemInput(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1, le=10)


class CompatibilityClaimInput(BaseModel):
    primary_product_id: str = Field(min_length=1, max_length=64)
    addon_product_id: str = Field(min_length=1, max_length=64)


class CreateCartRequest(BaseModel):
    items: list[CartItemInput] = Field(min_length=1, max_length=20)
    compatibility_claims: list[CompatibilityClaimInput] = Field(default_factory=list, max_length=10)

    @field_validator("items")
    @classmethod
    def unique_products(cls, items: list[CartItemInput]) -> list[CartItemInput]:
        ids = [item.product_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate product IDs are not allowed")
        return items

    @field_validator("compatibility_claims")
    @classmethod
    def unique_compatibility_claims(
        cls, claims: list[CompatibilityClaimInput]
    ) -> list[CompatibilityClaimInput]:
        pairs = [(claim.primary_product_id, claim.addon_product_id) for claim in claims]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate compatibility claims are not allowed")
        if any(primary == addon for primary, addon in pairs):
            raise ValueError("a product cannot be its own add-on")
        return claims


class CartItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    product_name: str
    product_version: int
    quantity: int
    unit_price_paise: int
    line_total_paise: int


class CompatibilityClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    primary_product_id: str
    addon_product_id: str
    rule_id: str


class CartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    currency: str
    subtotal_paise: int
    total_paise: int
    cart_hash: str | None
    frozen_at: datetime | None
    expires_at: datetime | None
    approved_at: datetime | None
    version: int
    items: list[CartItemResponse]
    compatibility_claims: list[CompatibilityClaimResponse]


class ApproveCartRequest(BaseModel):
    cart_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class CreateOrderRequest(BaseModel):
    cart_id: str = Field(min_length=36, max_length=36)
    cart_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(min_length=8, max_length=100)


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    cart_id: str
    status: str
    currency: str
    total_paise: int
    cart_hash: str
    provider_order_id: str | None
    provider_payment_id: str | None
    paid_at: datetime | None


class ErrorResponse(BaseModel):
    error: str
    message: str
