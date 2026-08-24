from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GrowthEventRequest(BaseModel):
    session_id: str | None = Field(default=None, max_length=36)
    cart_id: str | None = Field(default=None, max_length=36)
    primary_product_id: str = Field(min_length=1, max_length=64)
    addon_product_id: str = Field(min_length=1, max_length=64)
    event_type: Literal["exposed", "accepted", "rejected"]
    baseline_paise: int = Field(ge=0)
    suggested_paise: int = Field(ge=0)


class GrowthEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    realised_uplift_paise: int
    data_mode: str
    created_at: datetime


class GrowthLedgerResponse(BaseModel):
    data_mode: Literal["test_demo"] = "test_demo"
    exposures: int
    accepted: int
    rejected: int
    acceptance_rate_percent: float
    baseline_revenue_paise: int
    assisted_revenue_paise: int
    incremental_revenue_paise: int
    events: list[GrowthEventResponse]
