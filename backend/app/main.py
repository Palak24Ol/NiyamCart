import os
from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .agent_contracts import build_agent_catalog, build_agent_policy, payload_etag
from .agent_models import AgentSession
from .agent_schemas import AgentAuditResponse, AgentRunRequest, AgentRunResponse
from .agent_service import AgentConfig, load_agent_session, run_agent
from .catalog import seed_catalog
from .commerce import CommerceError, approve_cart, create_cart, create_order, freeze_cart, load_cart
from .commerce_models import Order
from .commerce_schemas import (
    ApproveCartRequest,
    CartResponse,
    CreateCartRequest,
    CreateOrderRequest,
    OrderResponse,
)
from .database import Database
from .models import Product
from .policy import PolicyDecision, PolicyEvaluationRequest, evaluate_policy
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

    @app.exception_handler(CommerceError)
    async def commerce_error_handler(_: Request, error: CommerceError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": error.code, "message": error.message},
        )

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

    @app.post("/api/carts", response_model=CartResponse, status_code=201, tags=["commerce"])
    def create_cart_route(request: CreateCartRequest, session: SessionDependency):
        return create_cart(session, request)

    @app.get("/api/carts/{cart_id}", response_model=CartResponse, tags=["commerce"])
    def get_cart_route(cart_id: str, session: SessionDependency):
        return load_cart(session, cart_id)

    @app.post("/api/carts/{cart_id}/freeze", response_model=CartResponse, tags=["commerce"])
    def freeze_cart_route(cart_id: str, session: SessionDependency):
        return freeze_cart(session, cart_id)

    @app.post("/api/carts/{cart_id}/approve", response_model=CartResponse, tags=["commerce"])
    def approve_cart_route(
        cart_id: str,
        request: ApproveCartRequest,
        session: SessionDependency,
    ):
        return approve_cart(session, cart_id, request.cart_hash)

    @app.post("/api/orders", response_model=OrderResponse, status_code=201, tags=["commerce"])
    def create_order_route(request: CreateOrderRequest, session: SessionDependency):
        return create_order(session, request)

    @app.get("/api/orders/{order_id}", response_model=OrderResponse, tags=["commerce"])
    def get_order_route(order_id: str, session: SessionDependency):
        order = session.get(Order, order_id)
        if order is None:
            raise CommerceError(404, "ORDER_NOT_FOUND", "Order not found")
        return order

    @app.get("/.well-known/agent-catalog.json", tags=["agent contracts"])
    def agent_catalog_route(request: Request, session: SessionDependency) -> Response:
        payload = build_agent_catalog(session)
        etag = payload_etag(payload)
        headers = {"ETag": etag, "Cache-Control": "public, max-age=60"}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return JSONResponse(content=payload, headers=headers)

    @app.get("/.well-known/agent-policy.json", tags=["agent contracts"])
    def agent_policy_route(request: Request) -> Response:
        payload = build_agent_policy()
        etag = payload_etag(payload)
        headers = {"ETag": etag, "Cache-Control": "public, max-age=300"}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return JSONResponse(content=payload, headers=headers)

    @app.post("/api/policy/evaluate", response_model=PolicyDecision, tags=["policy"])
    def evaluate_policy_route(request: PolicyEvaluationRequest) -> PolicyDecision:
        return evaluate_policy(request)

    @app.post(
        "/api/agent/sessions", response_model=AgentRunResponse, status_code=201, tags=["agent"]
    )
    def create_agent_session(request: AgentRunRequest, session: SessionDependency):
        return run_agent(session, request.message)

    @app.post(
        "/api/agent/sessions/{session_id}/messages",
        response_model=AgentRunResponse,
        tags=["agent"],
    )
    def revise_agent_session(session_id: str, request: AgentRunRequest, session: SessionDependency):
        agent_session = session.get(AgentSession, session_id)
        if agent_session is None:
            raise HTTPException(status_code=404, detail="Agent session not found")
        if agent_session.revision_count >= agent_session.max_revisions:
            raise HTTPException(status_code=409, detail="Agent revision budget exhausted")
        agent_session.revision_count += 1
        agent_session.status = "running"
        session.commit()
        return run_agent(
            session,
            request.message,
            config=AgentConfig.from_env(),
            agent_session=agent_session,
        )

    @app.get(
        "/api/agent/sessions/{session_id}/events",
        response_model=AgentAuditResponse,
        tags=["agent"],
    )
    def get_agent_audit(session_id: str, session: SessionDependency):
        agent_session = load_agent_session(session, session_id)
        if agent_session is None:
            raise HTTPException(status_code=404, detail="Agent session not found")
        return AgentAuditResponse(
            session_id=agent_session.id,
            status=agent_session.status,
            model=agent_session.model,
            step_count=agent_session.step_count,
            revision_count=agent_session.revision_count,
            estimated_cost_microusd=agent_session.estimated_cost_microusd,
            events=agent_session.events,
        )

    return app


app = create_app()
