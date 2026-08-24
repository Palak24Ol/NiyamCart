from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PaymentOfferResponse(BaseModel):
    key: str
    title: str
    payment_method: str
    terms: str
    savings_paise: int
    expected_payable_paise: int
    eligible: bool
    provider_configured: bool
    status: Literal["available", "preview", "ineligible", "standard"]
    reason: str


class PaymentOfferListResponse(BaseModel):
    cart_id: str
    cart_total_paise: int
    items: list[PaymentOfferResponse]
    count: int
    best_offer_key: str


class SelectPaymentOfferRequest(BaseModel):
    offer_key: str = Field(min_length=2, max_length=40)
    confirmed: bool


class SelectedPaymentOfferResponse(BaseModel):
    offer_key: str
    title: str
    payment_method: str
    savings_paise: int
    expected_payable_paise: int
    provider_configured: bool
    selected_at: datetime
