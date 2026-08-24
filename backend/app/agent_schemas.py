from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentRunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    original_message: str | None = Field(default=None, min_length=1, max_length=2000)
    language_code: str | None = Field(default=None, min_length=2, max_length=16)
    script_code: str | None = Field(default=None, min_length=4, max_length=8)
    message_is_normalized: bool = False
    synthesize_audio: bool = False


class AgentEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sequence: int
    event_type: str
    tool_name: str | None
    payload: dict[str, object]
    created_at: datetime


class AgentRunResponse(BaseModel):
    session_id: str
    status: Literal["completed", "escalated", "degraded", "budget_exhausted", "failed"]
    answer: str
    proposed_cart_id: str | None
    step_count: int
    revision_count: int
    estimated_cost_microusd: int
    recommended_product_ids: list[str] = Field(default_factory=list, max_length=8)
    language_code: str = "en-IN"
    script_code: str | None = None
    input_text: str | None = None
    audio_base64: str | None = None
    audio_mime_type: str | None = None
    localization_status: Literal["original", "localized", "unavailable"] = "original"
    voice_status: Literal["not_requested", "ready", "unavailable"] = "not_requested"
    policy_decision: Literal["allow", "deny", "escalate"] | None = None
    policy_rule_id: str | None = None


class AgentAuditResponse(BaseModel):
    session_id: str
    status: str
    model: str
    step_count: int
    revision_count: int
    estimated_cost_microusd: int
    events: list[AgentEventResponse]


class SearchCatalogArgs(BaseModel):
    query: str = Field(min_length=1, max_length=120)
    category: str | None = Field(default=None, max_length=80)
    min_price_paise: int | None = Field(default=None, ge=0)
    max_price_paise: int | None = Field(default=None, ge=0)
    limit: int = Field(default=5, ge=1, le=10)


class ProductDetailsArgs(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)


class CompatibleAddonsArgs(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)
    limit: int = Field(default=3, ge=1, le=5)


class GetPolicyArgs(BaseModel):
    action: str | None = Field(default=None, max_length=80)
    rule_id: str | None = Field(default=None, max_length=80)


class ProposedCartItem(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1, le=10)


class ProposedCompatibilityClaim(BaseModel):
    primary_product_id: str = Field(min_length=1, max_length=64)
    addon_product_id: str = Field(min_length=1, max_length=64)


class ProposeCartArgs(BaseModel):
    items: list[ProposedCartItem] = Field(min_length=1, max_length=20)
    compatibility_claims: list[ProposedCompatibilityClaim] = Field(
        default_factory=list, max_length=1
    )
    buyer_budget_paise: int = Field(ge=0)

    @field_validator("items")
    @classmethod
    def unique_products(cls, items: list[ProposedCartItem]) -> list[ProposedCartItem]:
        product_ids = [item.product_id for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("duplicate product IDs are not allowed")
        return items

    @model_validator(mode="after")
    def claims_reference_cart_products(self) -> ProposeCartArgs:
        product_ids = {item.product_id for item in self.items}
        for claim in self.compatibility_claims:
            if claim.primary_product_id == claim.addon_product_id:
                raise ValueError("a product cannot be its own add-on")
            if {claim.primary_product_id, claim.addon_product_id} - product_ids:
                raise ValueError("compatibility claims must reference products in the cart")
        return self


class EscalateArgs(BaseModel):
    reason: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=500)
