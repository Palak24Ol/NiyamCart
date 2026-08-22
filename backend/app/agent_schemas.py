from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentRunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


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


class ProposeCartArgs(BaseModel):
    items: list[ProposedCartItem] = Field(min_length=1, max_length=20)
    buyer_budget_paise: int = Field(ge=0)

    @field_validator("items")
    @classmethod
    def unique_products(cls, items: list[ProposedCartItem]) -> list[ProposedCartItem]:
        product_ids = [item.product_id for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("duplicate product IDs are not allowed")
        return items


class EscalateArgs(BaseModel):
    reason: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=500)
