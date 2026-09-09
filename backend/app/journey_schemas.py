from datetime import UTC, date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)


class MemoryInput(StrictInput):
    name: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=20)
    preferredLanguage: str = Field(default="English", max_length=30)
    whatsappOptIn: bool = False
    use_for_agent: bool = False
    size: str = Field(default="", max_length=30)
    brands: list[str] = Field(default_factory=list, max_length=10)
    budget_paise: int | None = Field(default=None, ge=100, le=10_000_000)
    rejected_product_ids: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("brands", "rejected_product_ids")
    @classmethod
    def bounded_strings(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 80 for value in values):
            raise ValueError("Each value must contain 1–80 characters")
        return list(dict.fromkeys(value.strip() for value in values))


class MissionInput(StrictInput):
    title: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=3, max_length=1000)
    requirements: list[str] = Field(default_factory=list, max_length=4)
    budget_paise: int | None = Field(default=None, ge=100, le=10_000_000)
    deadline: date | None = None
    use_memory: bool = True

    @field_validator("requirements")
    @classmethod
    def short_requirements(cls, values: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 120 for item in values):
            raise ValueError("Each item request must contain 1–120 characters")
        return [item.strip() for item in values]

    @field_validator("deadline")
    @classmethod
    def future_deadline(cls, value: date | None) -> date | None:
        if value and value < datetime.now(UTC).date():
            raise ValueError("Choose today or a future delivery date")
        return value


class MissionRevision(MissionInput):
    expected_revision: int = Field(ge=0)


class PlanInput(StrictInput):
    expected_revision: int = Field(ge=0)


class SelectPlanInput(PlanInput):
    product_ids: list[str] = Field(min_length=1, max_length=4)


class TaskInput(StrictInput):
    kind: Literal["watch", "replenish", "recovery"]
    product_id: str | None = Field(default=None, max_length=64)
    order_id: str | None = Field(default=None, max_length=36)
    cart_id: str | None = Field(default=None, max_length=36)
    target_paise: int | None = Field(default=None, ge=100, le=10_000_000)
    interval_days: int = Field(default=30, ge=1, le=365)
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(days=90))
    consent: bool = False

    @field_validator("expires_at")
    @classmethod
    def bounded_expiry(cls, value: datetime) -> datetime:
        value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        if not datetime.now(UTC) < value <= datetime.now(UTC) + timedelta(days=366):
            raise ValueError("Expiry must be in the next 366 days")
        return value.replace(tzinfo=None)


class TaskAction(StrictInput):
    action: Literal["pause", "resume", "cancel", "check"]


class SupportInput(StrictInput):
    kind: Literal["support", "return", "exchange"]
    message: str = Field(min_length=3, max_length=1000)
    product_id: str | None = Field(default=None, max_length=64)
    replacement_product_id: str | None = Field(default=None, max_length=64)
    request_key: str = Field(min_length=8, max_length=100)


class ShipmentInput(StrictInput):
    event_id: str = Field(min_length=8, max_length=100)
    order_id: str = Field(min_length=36, max_length=36)
    status: Literal["confirmed", "shipped", "out_for_delivery", "delayed", "delivered"]
    detail: str = Field(min_length=3, max_length=500)
    occurred_at: datetime


class OrderQuestion(StrictInput):
    message: str = Field(min_length=3, max_length=1000)


class ExternalQuoteInput(StrictInput):
    product_ids: list[str] = Field(min_length=1, max_length=4)
    budget_paise: int = Field(ge=100, le=10_000_000)
    deadline: date | None = None
    request_key: str = Field(min_length=8, max_length=100)
