import os
from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .catalog import seed_catalog
from .database import Database
from .models import Product
from .schemas import HealthResponse, ProductListResponse, ProductResponse


def create_app(database_url: str | None = None) -> FastAPI:
    db = Database(database_url or os.getenv("DATABASE_URL", "sqlite:///./niyamcart.db"))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db.create_schema()
        with db.session_factory() as session:
            seed_catalog(session)
        yield
        db.close()

    app = FastAPI(
        title="NiyamCart Commerce API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.db = db

    def get_session() -> Generator[Session, None, None]:
        yield from db.session()

    SessionDependency = Annotated[Session, Depends(get_session)]

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="niyamcart-api")

    @app.get("/api/products", response_model=ProductListResponse, tags=["catalog"])
    def list_products(
        session: SessionDependency,
        query: str | None = Query(default=None, max_length=100),
        category: str | None = Query(default=None, max_length=80),
    ) -> ProductListResponse:
        statement = select(Product).order_by(Product.name)
        if category:
            statement = statement.where(Product.category == category)
        if query:
            pattern = f"%{query.strip()}%"
            statement = statement.where(
                or_(Product.name.ilike(pattern), Product.description.ilike(pattern))
            )
        products = list(session.scalars(statement))
        return ProductListResponse(items=products, count=len(products))

    @app.get("/api/products/{product_id}", response_model=ProductResponse, tags=["catalog"])
    def get_product(
        product_id: str,
        session: SessionDependency,
    ) -> Product:
        product = session.get(Product, product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

    return app


app = create_app()
