from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    audience: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    original_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    reviews: Mapped[int] = mapped_column(Integer, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_days: Mapped[int] = mapped_column(Integer, nullable=False)
    free_delivery: Mapped[bool] = mapped_column(Boolean, nullable=False)
    occasion: Mapped[str] = mapped_column(String(80), nullable=False)
    material: Mapped[str] = mapped_column(String(120), nullable=False)
    highlights: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    badges: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    specs: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    size_chart: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    return_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    image: Mapped[str] = mapped_column(String(180), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
