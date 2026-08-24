from typing import Literal

from pydantic import BaseModel, Field

from .commerce_schemas import CartResponse


class WhatsAppReviewRequest(BaseModel):
    cart_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    destination: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    consent: Literal[True]
    destination_confirmed: Literal[True]


class WhatsAppConfirmationRequest(BaseModel):
    destination: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    consent: Literal[True]
    destination_confirmed: Literal[True]


class WhatsAppHandoffResponse(BaseModel):
    status: Literal["ready_for_user_share", "sending", "sent", "delivery_failed", "disabled"]
    duplicate: bool
    template_name: str | None
    review_url: str | None
    share_text: str | None
    message: str
    provider_message_id: str | None = None
    destination_fingerprint: str | None = None


class WhatsAppReviewResponse(BaseModel):
    cart: CartResponse
    permits_financial_approval: Literal[False] = False
    message: str = "Review only. Approval and payment must happen in NiyamCart."
