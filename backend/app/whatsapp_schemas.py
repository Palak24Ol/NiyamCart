from typing import Literal

from pydantic import BaseModel, Field

from .commerce_schemas import CartResponse


class WhatsAppReviewRequest(BaseModel):
    cart_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    consent: Literal[True]


class WhatsAppHandoffResponse(BaseModel):
    status: Literal["ready_for_user_share", "disabled"]
    duplicate: bool
    template_name: str | None
    review_url: str | None
    share_text: str | None
    message: str


class WhatsAppReviewResponse(BaseModel):
    cart: CartResponse
    permits_financial_approval: Literal[False] = False
    message: str = "Review only. Approval and payment must happen in NiyamCart."
