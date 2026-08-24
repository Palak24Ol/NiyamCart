from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

CART_STATES = ("proposed", "frozen", "approved", "ordered", "expired", "invalidated")
ORDER_STATES = ("payment_pending", "paid", "payment_failed", "cancelled")
RAZORPAY_CHECKOUT_STATES = ("creating", "ready", "failed")
WEBHOOK_STATES = ("processing", "processed", "ignored", "retryable")


class Cart(Base):
    __tablename__ = "carts"
    __table_args__ = (
        CheckConstraint(f"status IN {CART_STATES}", name="ck_cart_status"),
        CheckConstraint("subtotal_paise >= 0", name="ck_cart_subtotal_nonnegative"),
        CheckConstraint("total_paise >= 0", name="ck_cart_total_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    subtotal_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    total_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    cart_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    items: Mapped[list[CartItem]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
        order_by="CartItem.product_id",
    )
    compatibility_claims: Mapped[list[CartCompatibilityClaim]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
        order_by="CartCompatibilityClaim.id",
    )
    order: Mapped[Order | None] = relationship(back_populates="cart", uselist=False)
    fulfillment: Mapped[CartFulfillment | None] = relationship(
        back_populates="cart", uselist=False, cascade="all, delete-orphan"
    )
    offer_selection: Mapped[CartOfferSelection | None] = relationship(
        back_populates="cart", uselist=False, cascade="all, delete-orphan"
    )
    intent_mandate: Mapped[CartIntentMandate | None] = relationship(
        back_populates="cart", uselist=False, cascade="all, delete-orphan"
    )


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),
        CheckConstraint("quantity > 0", name="ck_cart_item_quantity_positive"),
        CheckConstraint("unit_price_paise >= 0", name="ck_cart_item_price_nonnegative"),
        CheckConstraint("line_total_paise >= 0", name="ck_cart_item_total_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[str] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(160), nullable=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_paise: Mapped[int] = mapped_column(Integer, nullable=False)

    cart: Mapped[Cart] = relationship(back_populates="items")


class CartCompatibilityClaim(Base):
    __tablename__ = "cart_compatibility_claims"
    __table_args__ = (
        UniqueConstraint(
            "cart_id",
            "primary_product_id",
            "addon_product_id",
            name="uq_cart_compatibility_claim",
        ),
        CheckConstraint(
            "primary_product_id <> addon_product_id",
            name="ck_compatibility_distinct_products",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[str] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    primary_product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    addon_product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(80), nullable=False)

    cart: Mapped[Cart] = relationship(back_populates="compatibility_claims")


class CustomerAddress(Base):
    __tablename__ = "customer_addresses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(80), nullable=False)
    phone: Mapped[str] = mapped_column(String(16), nullable=False)
    line1: Mapped[str] = mapped_column(String(160), nullable=False)
    locality: Mapped[str] = mapped_column(String(120), nullable=False)
    landmark: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(80), nullable=False)
    pincode: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CartFulfillment(Base):
    __tablename__ = "cart_fulfillments"
    __table_args__ = (CheckConstraint("delivery_paise >= 0", name="ck_cart_delivery_nonnegative"),)

    cart_id: Mapped[str] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), primary_key=True
    )
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    address_id: Mapped[str] = mapped_column(ForeignKey("customer_addresses.id"), nullable=False)
    address_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    address_label: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(80), nullable=False)
    phone: Mapped[str] = mapped_column(String(16), nullable=False)
    line1: Mapped[str] = mapped_column(String(160), nullable=False)
    locality: Mapped[str] = mapped_column(String(120), nullable=False)
    landmark: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(80), nullable=False)
    pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    delivery_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    eta_min_days: Mapped[int] = mapped_column(Integer, nullable=False)
    eta_max_days: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    cart: Mapped[Cart] = relationship(back_populates="fulfillment")


class CartOfferSelection(Base):
    __tablename__ = "cart_offer_selections"

    cart_id: Mapped[str] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), primary_key=True
    )
    offer_key: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_offer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    savings_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_payable_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    cart: Mapped[Cart] = relationship(back_populates="offer_selection")


class CartIntentMandate(Base):
    __tablename__ = "cart_intent_mandates"

    cart_id: Mapped[str] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), primary_key=True
    )
    mandate_id: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    integrity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_request: Mapped[str] = mapped_column(String(2000), nullable=False)
    constraints_json: Mapped[str] = mapped_column(String(2000), nullable=False)
    payment_rule: Mapped[str] = mapped_column(String(30), nullable=False)
    max_addons: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    cart: Mapped[Cart] = relationship(back_populates="intent_mandate")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("cart_id", name="uq_order_cart"),
        UniqueConstraint("idempotency_key", name="uq_order_idempotency_key"),
        CheckConstraint(f"status IN {ORDER_STATES}", name="ck_order_status"),
        CheckConstraint("total_paise >= 0", name="ck_order_total_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="payment_pending")
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    cart_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    cart: Mapped[Cart] = relationship(back_populates="order")
    payment_events: Mapped[list[PaymentEvent]] = relationship(back_populates="order")


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    provider_event_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    order: Mapped[Order] = relationship(back_populates="payment_events")


class RazorpayCheckout(Base):
    __tablename__ = "razorpay_checkouts"
    __table_args__ = (
        CheckConstraint(f"state IN {RAZORPAY_CHECKOUT_STATES}", name="ck_razorpay_checkout_state"),
        CheckConstraint("amount_paise >= 0", name="ck_razorpay_amount_nonnegative"),
    )

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), primary_key=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    receipt: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    cart_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RazorpayWebhookReceipt(Base):
    __tablename__ = "razorpay_webhook_receipts"
    __table_args__ = (
        CheckConstraint(f"status IN {WEBHOOK_STATES}", name="ck_razorpay_webhook_status"),
    )

    event_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class GrowthEvent(Base):
    __tablename__ = "growth_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    cart_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    primary_product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    addon_product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    baseline_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    suggested_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    realised_uplift_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="test_demo")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
