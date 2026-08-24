from pydantic import BaseModel, Field


class RescueCartRequest(BaseModel):
    unavailable_product_ids: list[str] = Field(default_factory=list, max_length=5)
    simulate_inventory_change: bool = False


class RescueItemDiff(BaseModel):
    old_product_id: str
    old_product_name: str
    old_price_paise: int
    new_product_id: str
    new_product_name: str
    new_price_paise: int
    reason: str


class RescueCartResponse(BaseModel):
    previous_cart_id: str
    replacement_cart_id: str
    previous_approval_revoked: bool
    intent_preserved: bool
    price_delta_paise: int
    requires_new_review_and_approval: bool = True
    data_mode: str
    changes: list[RescueItemDiff]
