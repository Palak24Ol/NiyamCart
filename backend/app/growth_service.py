from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import append_audit
from .commerce_models import GrowthEvent
from .growth_schemas import GrowthEventRequest, GrowthLedgerResponse


def record_growth_event(db: Session, payload: GrowthEventRequest) -> GrowthEvent:
    uplift = (
        max(0, payload.suggested_paise - payload.baseline_paise)
        if payload.event_type == "accepted"
        else 0
    )
    event = GrowthEvent(
        id=str(uuid4()),
        session_id=payload.session_id,
        cart_id=payload.cart_id,
        primary_product_id=payload.primary_product_id,
        addon_product_id=payload.addon_product_id,
        event_type=payload.event_type,
        baseline_paise=payload.baseline_paise,
        suggested_paise=payload.suggested_paise,
        realised_uplift_paise=uplift,
        data_mode="test_demo",
    )
    db.add(event)
    append_audit(
        db,
        "growth_ledger",
        event.id,
        f"cross_sell_{payload.event_type}",
        {
            "session_id": payload.session_id,
            "cart_id": payload.cart_id,
            "primary_product_id": payload.primary_product_id,
            "addon_product_id": payload.addon_product_id,
            "baseline_paise": payload.baseline_paise,
            "suggested_paise": payload.suggested_paise,
            "realised_uplift_paise": uplift,
            "data_mode": "test_demo",
        },
    )
    db.commit()
    db.refresh(event)
    return event


def growth_ledger(db: Session) -> GrowthLedgerResponse:
    events = list(
        db.scalars(select(GrowthEvent).order_by(GrowthEvent.created_at.desc()).limit(100))
    )
    exposures = sum(event.event_type == "exposed" for event in events)
    accepted = sum(event.event_type == "accepted" for event in events)
    rejected = sum(event.event_type == "rejected" for event in events)
    accepted_events = [event for event in events if event.event_type == "accepted"]
    baseline = sum(event.baseline_paise for event in accepted_events)
    assisted = sum(event.suggested_paise for event in accepted_events)
    return GrowthLedgerResponse(
        exposures=exposures,
        accepted=accepted,
        rejected=rejected,
        acceptance_rate_percent=round(accepted / max(1, accepted + rejected) * 100, 1),
        baseline_revenue_paise=baseline,
        assisted_revenue_paise=assisted,
        incremental_revenue_paise=sum(event.realised_uplift_paise for event in accepted_events),
        events=events,
    )
