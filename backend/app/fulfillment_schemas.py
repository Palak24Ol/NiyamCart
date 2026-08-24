from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AddressInput(BaseModel):
    label: str = Field(min_length=2, max_length=20)
    recipient_name: str = Field(min_length=2, max_length=80)
    phone: str = Field(pattern=r"^\+91[6-9]\d{9}$")
    line1: str = Field(min_length=3, max_length=160)
    locality: str = Field(min_length=2, max_length=120)
    landmark: str | None = Field(default=None, max_length=120)
    city: str = Field(min_length=2, max_length=80)
    state: str = Field(min_length=2, max_length=80)
    pincode: str = Field(pattern=r"^[1-9]\d{5}$")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_default: bool = False

    @field_validator("label", "recipient_name", "line1", "locality", "landmark", "city", "state")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class AddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    recipient_name: str
    phone: str
    line1: str
    locality: str
    landmark: str | None
    city: str
    state: str
    pincode: str
    latitude: float | None
    longitude: float | None
    is_default: bool
    created_at: datetime


class AddressListResponse(BaseModel):
    items: list[AddressResponse]
    count: int


class CartDeliveryRequest(BaseModel):
    address_id: str = Field(min_length=36, max_length=36)
    confirmed: bool


class CartDeliveryResponse(BaseModel):
    address_id: str
    address_label: str
    city: str
    masked_pincode: str
    delivery_paise: int
    eta_min_days: int
    eta_max_days: int
    confirmed_at: datetime


class ReverseGeocodeRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    allow_public_provider: bool = False


class ReverseGeocodeResponse(BaseModel):
    display_name: str
    line1: str
    locality: str
    city: str
    state: str
    pincode: str
    latitude: float
    longitude: float
    approximate: bool = True
