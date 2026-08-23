from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from typing import Protocol

import httpx

SARVAM_BASE_URL = "https://api.sarvam.ai"
MAX_AUDIO_BYTES = 5 * 1024 * 1024
SUPPORTED_AUDIO_TYPES = {
    "audio/aac",
    "audio/flac",
    "audio/m4a",
    "audio/mp3",
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "audio/opus",
    "audio/wav",
    "audio/webm",
    "audio/x-m4a",
    "audio/x-wav",
}
TTS_LANGUAGE_CODES = {
    "bn-IN",
    "en-IN",
    "gu-IN",
    "hi-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "od-IN",
    "pa-IN",
    "ta-IN",
    "te-IN",
}


class SarvamError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 502) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class PreparedText:
    original_text: str
    normalized_text: str
    language_code: str
    script_code: str | None = None
    language_probability: float | None = None


class SarvamProvider(Protocol):
    def prepare_text(
        self,
        text: str,
        language_code: str | None = None,
        script_code: str | None = None,
    ) -> PreparedText: ...

    def transcribe(self, audio: bytes, content_type: str) -> PreparedText: ...

    def localize(self, text: str, language_code: str, script_code: str | None) -> str: ...

    def synthesize(self, text: str, language_code: str) -> tuple[str, str]: ...


def _plain_text(value: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
    text = re.sub(r"[`#]", "", text)
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text).strip()


def _detect_script(text: str) -> str:
    ranges = [
        ("Deva", "\u0900", "\u097f"),
        ("Beng", "\u0980", "\u09ff"),
        ("Guru", "\u0a00", "\u0a7f"),
        ("Gujr", "\u0a80", "\u0aff"),
        ("Orya", "\u0b00", "\u0b7f"),
        ("Taml", "\u0b80", "\u0bff"),
        ("Telu", "\u0c00", "\u0c7f"),
        ("Knda", "\u0c80", "\u0cff"),
        ("Mlym", "\u0d00", "\u0d7f"),
    ]
    for code, start, end in ranges:
        if any(start <= character <= end for character in text):
            return code
    return "Latn"


@dataclass(frozen=True)
class SarvamSettings:
    api_key: str
    stt_model: str = "saaras:v3"
    tts_model: str = "bulbul:v3"
    tts_speaker: str = "shubh"
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> SarvamSettings | None:
        enabled = os.getenv("SARVAM_VOICE_ENABLED", "false").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        api_key = os.getenv("SARVAM_API_KEY", "").strip()
        if not enabled or not api_key:
            return None
        return cls(
            api_key=api_key,
            stt_model=os.getenv("SARVAM_STT_MODEL", "saaras:v3").strip(),
            tts_model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v3").strip(),
            tts_speaker=os.getenv("SARVAM_TTS_SPEAKER", "shubh").strip(),
            timeout_seconds=max(float(os.getenv("SARVAM_TIMEOUT_SECONDS", "30")), 1.0),
        )


class SarvamClient:
    def __init__(self, settings: SarvamSettings) -> None:
        self.settings = settings

    @property
    def _headers(self) -> dict[str, str]:
        return {"api-subscription-key": self.settings.api_key}

    def _post(self, path: str, **kwargs: object) -> dict[str, object]:
        try:
            response = httpx.post(
                f"{SARVAM_BASE_URL}{path}",
                headers=self._headers,
                timeout=self.settings.timeout_seconds,
                **kwargs,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Sarvam returned an invalid response")
            return payload
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status == 403:
                message = "The Sarvam API key was rejected."
            elif status == 429:
                message = "Sarvam's request limit was reached. Please try again shortly."
            else:
                message = "Sarvam could not process this request."
            raise SarvamError("SARVAM_REQUEST_FAILED", message, status_code=502) from error
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise SarvamError(
                "SARVAM_UNAVAILABLE",
                "Sarvam is temporarily unavailable; text chat is still available.",
            ) from error

    def _translate(
        self,
        text: str,
        source: str,
        target: str,
        *,
        roman_output: bool = False,
    ) -> str:
        if source == target:
            return text
        payload: dict[str, object] = {
            "input": text[:1000],
            "source_language_code": source,
            "target_language_code": target,
            "model": "mayura:v1",
            "mode": "code-mixed" if roman_output else "modern-colloquial",
            "numerals_format": "international",
        }
        if roman_output:
            payload["output_script"] = "roman"
        response = self._post("/translate", json=payload)
        translated = str(response.get("translated_text", "")).strip()
        if not translated:
            raise SarvamError("EMPTY_TRANSLATION", "Sarvam returned an empty translation.")
        return translated

    def prepare_text(
        self,
        text: str,
        language_code: str | None = None,
        script_code: str | None = None,
    ) -> PreparedText:
        original = text.strip()
        if not original:
            raise SarvamError("EMPTY_TRANSCRIPT", "No speech was detected.", status_code=422)
        detected_language = language_code
        detected_script = script_code
        if not detected_language or detected_language in {"auto", "unknown"}:
            response = self._post("/text-lid", json={"input": original[:1000]})
            detected_language = str(response.get("language_code") or "en-IN")
            detected_script = str(response.get("script_code") or _detect_script(original))
        detected_script = detected_script or _detect_script(original)
        normalized = (
            original
            if detected_language == "en-IN"
            else self._translate(original, detected_language, "en-IN")
        )
        return PreparedText(original, normalized, detected_language, detected_script)

    def transcribe(self, audio: bytes, content_type: str) -> PreparedText:
        clean_type = content_type.split(";", 1)[0].strip().lower()
        if clean_type not in SUPPORTED_AUDIO_TYPES:
            raise SarvamError(
                "UNSUPPORTED_AUDIO",
                "Recordings must be WebM, WAV, MP3, MP4, AAC, FLAC, OGG, or Opus audio.",
                status_code=415,
            )
        if not audio:
            raise SarvamError("EMPTY_AUDIO", "The recording was empty.", status_code=422)
        if len(audio) > MAX_AUDIO_BYTES:
            raise SarvamError(
                "AUDIO_TOO_LARGE",
                "The recording is too large. Keep voice questions under 25 seconds.",
                status_code=413,
            )
        extension = clean_type.split("/", 1)[1].replace("x-", "").replace("mpeg", "mp3")
        response = self._post(
            "/speech-to-text",
            data={
                "model": self.settings.stt_model,
                "language_code": "unknown",
                "mode": "transcribe",
            },
            files={"file": (f"niyam-voice.{extension}", audio, clean_type)},
        )
        transcript = str(response.get("transcript", "")).strip()
        language = str(response.get("language_code") or "en-IN")
        probability = response.get("language_probability")
        prepared = self.prepare_text(transcript, language, _detect_script(transcript))
        return PreparedText(
            prepared.original_text,
            prepared.normalized_text,
            prepared.language_code,
            prepared.script_code,
            float(probability) if isinstance(probability, (int, float)) else None,
        )

    def localize(self, text: str, language_code: str, script_code: str | None) -> str:
        plain = _plain_text(text)
        if language_code == "en-IN":
            return plain
        return self._translate(
            plain,
            "en-IN",
            language_code,
            roman_output=script_code == "Latn",
        )

    def synthesize(self, text: str, language_code: str) -> tuple[str, str]:
        if language_code not in TTS_LANGUAGE_CODES:
            raise SarvamError(
                "TTS_LANGUAGE_UNSUPPORTED",
                "Text is available, but Sarvam voice output is not available for this language.",
                status_code=422,
            )
        response = self._post(
            "/text-to-speech",
            json={
                "text": _plain_text(text)[:2500],
                "language_code": language_code,
                "speaker": self.settings.tts_speaker,
                "model": self.settings.tts_model,
                "output_audio_codec": "wav",
            },
        )
        audios = response.get("audios")
        if not isinstance(audios, list) or not audios:
            raise SarvamError("EMPTY_AUDIO_RESPONSE", "Sarvam returned no answer audio.")
        encoded = "".join(str(item) for item in audios)
        try:
            base64.b64decode(encoded, validate=True)
        except ValueError as error:
            raise SarvamError(
                "INVALID_AUDIO_RESPONSE",
                "Sarvam returned invalid answer audio.",
            ) from error
        return encoded, "audio/wav"


def configured_sarvam() -> SarvamClient | None:
    settings = SarvamSettings.from_env()
    return SarvamClient(settings) if settings else None
