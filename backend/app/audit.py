from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base

GENESIS_HASH = "0" * 64
SENSITIVE_KEY_MARKERS = (
    "authorization",
    "card",
    "cvv",
    "password",
    "secret",
    "signature",
    "token",
)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "sequence", name="uq_audit_scope_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sequence: int
    event_type: str
    payload: dict[str, object]
    previous_hash: str
    event_hash: str
    created_at: datetime


class AuditVerificationResponse(BaseModel):
    scope_type: str
    scope_id: str
    valid: bool
    event_count: int
    root_hash: str
    events: list[AuditEventResponse]


def _redact_string(value: str) -> str:
    value = re.sub(r"rzp_(?:test|live)_[A-Za-z0-9]+", "[REDACTED_KEY]", value)
    value = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[REDACTED_EMAIL]",
        value,
    )
    value = re.sub(
        r"(?<![A-Za-z0-9])\+?\d(?:[\s-]?\d){9,18}(?![A-Za-z0-9])",
        "[REDACTED_NUMBER]",
        value,
    )
    return value[:2000]


def redact(value: object, key: str = "") -> object:
    lowered = key.lower()
    if any(marker in lowered for marker in SENSITIVE_KEY_MARKERS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(item_key): redact(item_value, str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value[:50]]
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return _redact_string(str(value))


def _hash_material(
    scope_type: str,
    scope_id: str,
    sequence: int,
    event_type: str,
    payload: dict[str, object],
    previous_hash: str,
) -> str:
    material = {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "sequence": sequence,
        "event_type": event_type,
        "payload": payload,
        "previous_hash": previous_hash,
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def append_audit(
    db: Session,
    scope_type: str,
    scope_id: str,
    event_type: str,
    payload: dict[str, object],
) -> AuditEvent:
    with db.no_autoflush:
        previous = db.scalar(
            select(AuditEvent)
            .where(AuditEvent.scope_type == scope_type, AuditEvent.scope_id == scope_id)
            .order_by(AuditEvent.sequence.desc())
            .limit(1)
        )
    sequence = previous.sequence + 1 if previous else 1
    previous_hash = previous.event_hash if previous else GENESIS_HASH
    safe_payload = redact(payload)
    if not isinstance(safe_payload, dict):
        safe_payload = {"value": safe_payload}
    event = AuditEvent(
        scope_type=scope_type,
        scope_id=scope_id,
        sequence=sequence,
        event_type=event_type,
        payload=safe_payload,
        previous_hash=previous_hash,
        event_hash=_hash_material(
            scope_type,
            scope_id,
            sequence,
            event_type,
            safe_payload,
            previous_hash,
        ),
    )
    db.add(event)
    return event


def verify_audit(db: Session, scope_type: str, scope_id: str) -> AuditVerificationResponse:
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.scope_type == scope_type, AuditEvent.scope_id == scope_id)
            .order_by(AuditEvent.sequence)
        )
    )
    expected_previous = GENESIS_HASH
    valid = True
    for expected_sequence, event in enumerate(events, start=1):
        expected_hash = _hash_material(
            event.scope_type,
            event.scope_id,
            event.sequence,
            event.event_type,
            event.payload,
            event.previous_hash,
        )
        if (
            event.sequence != expected_sequence
            or event.previous_hash != expected_previous
            or event.event_hash != expected_hash
        ):
            valid = False
        expected_previous = event.event_hash
    return AuditVerificationResponse(
        scope_type=scope_type,
        scope_id=scope_id,
        valid=valid,
        event_count=len(events),
        root_hash=events[-1].event_hash if events else GENESIS_HASH,
        events=events,
    )
