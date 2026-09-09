"""Additive journey tables: existing commerce rows and payment authority are unchanged."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .commerce import utc_now
from .database import Base


class BuyerMemory(Base):
    __tablename__ = "buyer_memories"
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class ShoppingMission(Base):
    __tablename__ = "shopping_missions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    revision: Mapped[int] = mapped_column(Integer, default=0)
    request: Mapped[dict] = mapped_column(JSON, default=dict)
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    messages: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class JourneyCart(Base):
    __tablename__ = "journey_carts"
    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id"), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    mission_id: Mapped[str | None] = mapped_column(ForeignKey("shopping_missions.id"))
    source: Mapped[str] = mapped_column(String(40), default="mission")
    budget_paise: Mapped[int | None] = mapped_column(Integer)
    deadline: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class JourneyTask(Base):
    __tablename__ = "journey_tasks"
    __table_args__ = (UniqueConstraint("customer_id", "dedupe_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    dedupe_key: Mapped[str] = mapped_column(String(160))
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    next_run: Mapped[datetime] = mapped_column(DateTime, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    failures: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class JourneyNotice(Base):
    __tablename__ = "journey_notices"
    __table_args__ = (UniqueConstraint("customer_id", "dedupe_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(String(1000))
    href: Mapped[str] = mapped_column(String(240))
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ShipmentEvent(Base):
    __tablename__ = "journey_shipment_events"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class SupportCase(Base):
    __tablename__ = "journey_support_cases"
    __table_args__ = (UniqueConstraint("customer_id", "request_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="draft")
    request_key: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class BuyerAccessKey(Base):
    __tablename__ = "journey_buyer_keys"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class ExternalBuyerQuote(Base):
    __tablename__ = "journey_external_quotes"
    __table_args__ = (UniqueConstraint("customer_id", "request_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    access_digest: Mapped[str] = mapped_column(String(64), index=True)
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id"))
    quote: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
