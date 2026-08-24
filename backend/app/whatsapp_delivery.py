from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class WhatsAppDelivery:
    provider_message_id: str
    provider_status: str


class WhatsAppDeliveryError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class WhatsAppSender(Protocol):
    def send(
        self,
        *,
        kind: str,
        destination: str,
        body: str,
        variables: dict[str, str],
    ) -> WhatsAppDelivery: ...


@dataclass(frozen=True)
class TwilioSettings:
    account_sid: str
    auth_token: str
    from_address: str
    review_content_sid: str = ""
    confirmation_content_sid: str = ""

    @classmethod
    def from_env(cls) -> TwilioSettings | None:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        from_address = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()
        if not account_sid and not auth_token and not from_address:
            return None
        if not account_sid.startswith("AC") or len(account_sid) != 34:
            raise RuntimeError("TWILIO_ACCOUNT_SID must be a valid Account SID")
        if len(auth_token) < 24:
            raise RuntimeError("TWILIO_AUTH_TOKEN is missing or invalid")
        if not re.fullmatch(r"whatsapp:\+[1-9]\d{7,14}", from_address):
            raise RuntimeError("TWILIO_WHATSAPP_FROM must use whatsapp:+E164 format")
        return cls(
            account_sid=account_sid,
            auth_token=auth_token,
            from_address=from_address,
            review_content_sid=os.getenv("TWILIO_REVIEW_CONTENT_SID", "").strip(),
            confirmation_content_sid=os.getenv("TWILIO_CONFIRMATION_CONTENT_SID", "").strip(),
        )


class TwilioWhatsAppSender:
    def __init__(self, settings: TwilioSettings) -> None:
        self.settings = settings

    def send(
        self,
        *,
        kind: str,
        destination: str,
        body: str,
        variables: dict[str, str],
    ) -> WhatsAppDelivery:
        content_sid = (
            self.settings.review_content_sid
            if kind == "cart_review"
            else self.settings.confirmation_content_sid
        )
        payload: dict[str, str] = {
            "From": self.settings.from_address,
            "To": f"whatsapp:{destination}",
        }
        if content_sid:
            payload["ContentSid"] = content_sid
            payload["ContentVariables"] = json.dumps(variables, separators=(",", ":"))
        else:
            payload["Body"] = body
        try:
            response = httpx.post(
                "https://api.twilio.com/2010-04-01/Accounts/"
                f"{self.settings.account_sid}/Messages.json",
                auth=(self.settings.account_sid, self.settings.auth_token),
                data=payload,
                timeout=10.0,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise WhatsAppDeliveryError("TWILIO_UNAVAILABLE") from error
        message_sid = result.get("sid")
        if not isinstance(message_sid, str) or not message_sid.startswith("SM"):
            raise WhatsAppDeliveryError("INVALID_TWILIO_RESPONSE")
        return WhatsAppDelivery(
            provider_message_id=message_sid,
            provider_status=str(result.get("status", "accepted")),
        )


def configured_sender() -> WhatsAppSender | None:
    settings = TwilioSettings.from_env()
    return TwilioWhatsAppSender(settings) if settings else None
