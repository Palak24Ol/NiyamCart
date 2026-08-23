import os
from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .agent_contracts import build_agent_catalog, build_agent_policy, payload_etag
from .agent_models import AgentSession
from .agent_schemas import AgentAuditResponse, AgentRunRequest, AgentRunResponse
from .agent_service import AgentConfig, load_agent_session, run_agent
from .audit import AuditVerificationResponse, verify_audit
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
from .razorpay_schemas import (
    PaymentVerificationResponse,
    RazorpayCheckoutResponse,
    RazorpayWebhookResponse,
    VerifyRazorpayPaymentRequest,
)
from .razorpay_service import (
    RazorpayError,
    RazorpayGateway,
    configured_gateway,
    create_razorpay_checkout,
    process_razorpay_webhook,
    verify_checkout_payment,
)
from .sarvam_service import PreparedText, SarvamError, SarvamProvider, configured_sarvam
from .schemas import HealthResponse, ProductListResponse, ProductResponse
from .voice_schemas import (
    SpeechSynthesisRequest,
    SpeechSynthesisResponse,
    VoiceTranscriptionResponse,
)
from .whatsapp_delivery import WhatsAppSender, configured_sender
from .whatsapp_schemas import (
    WhatsAppConfirmationRequest,
    WhatsAppHandoffResponse,
    WhatsAppReviewRequest,
    WhatsAppReviewResponse,
)
from .whatsapp_service import (
    WhatsAppSettings,
    load_review_cart,
    prepare_cart_review_handoff,
    prepare_payment_confirmation_handoff,
)


def create_app(
    database_url: str | None = None,
    razorpay_gateway: RazorpayGateway | None = None,
    whatsapp_settings: WhatsAppSettings | None = None,
    whatsapp_sender: WhatsAppSender | None = None,
    sarvam_provider: SarvamProvider | None = None,
) -> FastAPI:
    db = Database(database_url or os.getenv("DATABASE_URL", "sqlite:///./niyamcart.db"))
    gateway = razorpay_gateway if razorpay_gateway is not None else configured_gateway()
    handoff_settings = whatsapp_settings or WhatsAppSettings.from_env()
    handoff_sender = (
        whatsapp_sender
        if whatsapp_sender is not None
        else (configured_sender() if whatsapp_settings is None else None)
    )
    speech = sarvam_provider if sarvam_provider is not None else configured_sarvam()

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
    frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["content-type"],
    )
    app.state.db = db
    app.state.razorpay_gateway = gateway
    app.state.whatsapp_settings = handoff_settings
    app.state.whatsapp_sender = handoff_sender
    app.state.sarvam_provider = speech

    def get_session() -> Generator[Session, None, None]:
        yield from db.session()

    SessionDependency = Annotated[Session, Depends(get_session)]

    @app.exception_handler(CommerceError)
    async def commerce_error_handler(_: Request, error: CommerceError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": error.code, "message": error.message},
        )

    @app.exception_handler(RazorpayError)
    async def razorpay_error_handler(_: Request, error: RazorpayError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": error.code, "message": error.message},
        )

    @app.exception_handler(SarvamError)
    async def sarvam_error_handler(_: Request, error: SarvamError) -> JSONResponse:
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

    @app.post(
        "/api/orders/{order_id}/razorpay-checkout",
        response_model=RazorpayCheckoutResponse,
        status_code=201,
        tags=["payments"],
    )
    def create_razorpay_checkout_route(order_id: str, session: SessionDependency):
        return create_razorpay_checkout(session, order_id, app.state.razorpay_gateway)

    @app.post(
        "/api/payments/razorpay/verify",
        response_model=PaymentVerificationResponse,
        tags=["payments"],
    )
    def verify_razorpay_payment_route(
        payload: VerifyRazorpayPaymentRequest, session: SessionDependency
    ):
        return verify_checkout_payment(session, payload, app.state.razorpay_gateway)

    @app.post(
        "/api/payments/razorpay/webhook",
        response_model=RazorpayWebhookResponse,
        tags=["payments"],
    )
    async def razorpay_webhook_route(request: Request, session: SessionDependency):
        raw_body = await request.body()
        return process_razorpay_webhook(
            session,
            raw_body,
            request.headers.get("x-razorpay-signature", ""),
            request.headers.get("x-razorpay-event-id", ""),
            app.state.razorpay_gateway,
        )

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

    def prepare_agent_text(request: AgentRunRequest) -> PreparedText:
        original = request.original_message or request.message
        if request.message_is_normalized:
            return PreparedText(
                original,
                request.message,
                request.language_code or "en-IN",
                request.script_code,
            )
        if app.state.sarvam_provider is None:
            return PreparedText(original, request.message, request.language_code or "en-IN")
        try:
            return app.state.sarvam_provider.prepare_text(
                request.message,
                request.language_code,
                request.script_code,
            )
        except SarvamError:
            return PreparedText(original, request.message, request.language_code or "en-IN")

    def localize_agent_result(
        result: AgentRunResponse,
        prepared: PreparedText,
        synthesize_audio: bool,
    ) -> AgentRunResponse:
        result.language_code = prepared.language_code
        result.script_code = prepared.script_code
        result.input_text = prepared.original_text
        provider = app.state.sarvam_provider
        if provider is None:
            if synthesize_audio:
                result.voice_status = "unavailable"
            return result
        try:
            localized = provider.localize(
                result.answer,
                prepared.language_code,
                prepared.script_code,
            )
            result.answer = localized
            result.localization_status = (
                "original" if prepared.language_code == "en-IN" else "localized"
            )
        except SarvamError:
            result.localization_status = "unavailable"
        if synthesize_audio:
            try:
                result.audio_base64, result.audio_mime_type = provider.synthesize(
                    result.answer,
                    prepared.language_code,
                )
                result.voice_status = "ready"
            except SarvamError:
                result.voice_status = "unavailable"
        return result

    def execute_agent_request(
        request: AgentRunRequest,
        session: Session,
        agent_session: AgentSession | None = None,
    ) -> AgentRunResponse:
        prepared = prepare_agent_text(request)
        result = run_agent(
            session,
            prepared.normalized_text,
            config=AgentConfig.from_env(),
            agent_session=agent_session,
            original_message=prepared.original_text,
            language_code=prepared.language_code,
        )
        return localize_agent_result(result, prepared, request.synthesize_audio)

    @app.post(
        "/api/agent/sessions", response_model=AgentRunResponse, status_code=201, tags=["agent"]
    )
    def create_agent_session(request: AgentRunRequest, session: SessionDependency):
        return execute_agent_request(request, session)

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
        return execute_agent_request(request, session, agent_session)

    @app.post(
        "/api/voice/transcribe",
        response_model=VoiceTranscriptionResponse,
        tags=["voice"],
    )
    def transcribe_voice(
        audio: Annotated[bytes, Body(media_type="application/octet-stream")],
        content_type: Annotated[str | None, Header()] = None,
    ) -> VoiceTranscriptionResponse:
        provider = app.state.sarvam_provider
        if provider is None:
            raise SarvamError(
                "SARVAM_NOT_CONFIGURED",
                "Voice chat is not configured; typed chat is still available.",
                status_code=503,
            )
        prepared = provider.transcribe(audio, content_type or "application/octet-stream")
        return VoiceTranscriptionResponse(
            transcript=prepared.original_text,
            normalized_text=prepared.normalized_text,
            language_code=prepared.language_code,
            script_code=prepared.script_code,
            language_probability=prepared.language_probability,
        )

    @app.post(
        "/api/voice/synthesize",
        response_model=SpeechSynthesisResponse,
        tags=["voice"],
    )
    def synthesize_voice(request: SpeechSynthesisRequest) -> SpeechSynthesisResponse:
        provider = app.state.sarvam_provider
        if provider is None:
            raise SarvamError(
                "SARVAM_NOT_CONFIGURED",
                "Spoken answers are not configured; the text answer remains available.",
                status_code=503,
            )
        audio_base64, audio_mime_type = provider.synthesize(
            request.text,
            request.language_code,
        )
        return SpeechSynthesisResponse(
            audio_base64=audio_base64,
            audio_mime_type=audio_mime_type,
            language_code=request.language_code,
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

    @app.get(
        "/api/audit/{scope_type}/{scope_id}",
        response_model=AuditVerificationResponse,
        tags=["audit"],
    )
    def verify_audit_route(
        scope_type: str,
        scope_id: str,
        session: SessionDependency,
    ) -> AuditVerificationResponse:
        if scope_type not in {"agent_session", "cart", "order"}:
            raise HTTPException(status_code=404, detail="Unknown audit scope")
        result = verify_audit(session, scope_type, scope_id)
        if result.event_count == 0:
            raise HTTPException(status_code=404, detail="Audit trail not found")
        return result

    @app.post(
        "/api/carts/{cart_id}/whatsapp-review",
        response_model=WhatsAppHandoffResponse,
        tags=["notifications"],
    )
    def prepare_whatsapp_review_route(
        cart_id: str,
        request: WhatsAppReviewRequest,
        session: SessionDependency,
    ) -> WhatsAppHandoffResponse:
        return prepare_cart_review_handoff(
            session,
            cart_id,
            request,
            app.state.whatsapp_settings,
            app.state.whatsapp_sender,
        )

    @app.get(
        "/api/notifications/whatsapp/review/{token}",
        response_model=WhatsAppReviewResponse,
        tags=["notifications"],
    )
    def open_whatsapp_review_route(
        token: str,
        session: SessionDependency,
    ) -> WhatsAppReviewResponse:
        return WhatsAppReviewResponse(
            cart=load_review_cart(session, token, app.state.whatsapp_settings)
        )

    @app.post(
        "/api/orders/{order_id}/whatsapp-confirmation",
        response_model=WhatsAppHandoffResponse,
        tags=["notifications"],
    )
    def prepare_whatsapp_confirmation_route(
        order_id: str,
        request: WhatsAppConfirmationRequest,
        session: SessionDependency,
    ) -> WhatsAppHandoffResponse:
        return prepare_payment_confirmation_handoff(
            session,
            order_id,
            request,
            app.state.whatsapp_settings,
            app.state.whatsapp_sender,
        )

    return app


app = create_app()
