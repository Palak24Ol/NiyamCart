import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth_models import Customer, CustomerSession

SESSION_COOKIE = "niyamcart_session"
SESSION_DAYS = 7


class AuthError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _password_hash(password: str, salt: bytes | None = None) -> str:
    actual_salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=actual_salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${actual_salt.hex()}${digest.hex()}"


def _password_matches(password: str, stored: str) -> bool:
    try:
        algorithm, salt_hex, _ = stored.split("$", 2)
        if algorithm != "scrypt":
            return False
        candidate = _password_hash(password, bytes.fromhex(salt_hex))
        return hmac.compare_digest(candidate, stored)
    except (ValueError, TypeError):
        return False


def create_customer(db: Session, name: str, email: str, password: str) -> Customer:
    customer = Customer(
        id=str(uuid4()), name=name, email=email, password_hash=_password_hash(password)
    )
    db.add(customer)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise AuthError(
            409,
            "EMAIL_ALREADY_REGISTERED",
            "An account already exists for this email",
        ) from error
    db.refresh(customer)
    return customer


def authenticate_customer(db: Session, email: str, password: str) -> Customer:
    customer = db.scalar(select(Customer).where(Customer.email == email))
    if customer is None or not _password_matches(password, customer.password_hash):
        raise AuthError(401, "INVALID_CREDENTIALS", "Email or password is incorrect")
    return customer


def create_session(db: Session, customer: Customer) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=SESSION_DAYS)
    db.add(
        CustomerSession(
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            customer_id=customer.id,
            expires_at=expires_at,
        )
    )
    db.commit()
    return token, expires_at


def load_customer_from_token(db: Session, token: str | None) -> Customer:
    if not token:
        raise AuthError(401, "AUTHENTICATION_REQUIRED", "Please sign in to continue")
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    customer_session = db.get(CustomerSession, token_hash)
    now = datetime.now(UTC)
    if customer_session is None:
        raise AuthError(401, "INVALID_SESSION", "Please sign in again")
    expires_at = customer_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        db.delete(customer_session)
        db.commit()
        raise AuthError(401, "SESSION_EXPIRED", "Your session expired. Please sign in again")
    customer = db.get(Customer, customer_session.customer_id)
    if customer is None:
        raise AuthError(401, "INVALID_SESSION", "Please sign in again")
    return customer


def delete_session(db: Session, token: str | None) -> None:
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db.execute(delete(CustomerSession).where(CustomerSession.token_hash == token_hash))
    db.commit()


def secure_cookie_enabled() -> bool:
    return os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
