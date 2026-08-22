from typing import Literal

from pydantic import BaseModel, Field


class RazorpayCheckoutResponse(BaseModel):
    internal_order_id: str
    razorpay_order_id: str
    key_id: str
    amount_paise: int
    currency: str
    merchant_name: str = "NiyamCart"
    description: str = "NiyamCart test-mode checkout"
    test_mode: Literal[True] = True


class VerifyRazorpayPaymentRequest(BaseModel):
    internal_order_id: str = Field(min_length=36, max_length=36)
    razorpay_order_id: str = Field(pattern=r"^order_[A-Za-z0-9]+$", max_length=100)
    razorpay_payment_id: str = Field(pattern=r"^pay_[A-Za-z0-9]+$", max_length=100)
    razorpay_signature: str = Field(pattern=r"^[a-fA-F0-9]{64}$")


class PaymentVerificationResponse(BaseModel):
    internal_order_id: str
    status: str
    payment_status: Literal["verified"]
    razorpay_payment_id: str
    duplicate: bool


class RazorpayWebhookResponse(BaseModel):
    status: Literal["ok"] = "ok"
    duplicate: bool
    processed: bool
    reason: str
