from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VoiceTranscriptionResponse(BaseModel):
    transcript: str
    normalized_text: str
    language_code: str
    script_code: str | None = None
    language_probability: float | None = None


class SpeechSynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2500)
    language_code: str = Field(default="en-IN", min_length=2, max_length=16)


class SpeechSynthesisResponse(BaseModel):
    audio_base64: str
    audio_mime_type: str = "audio/wav"
    language_code: str
    voice_status: Literal["ready"] = "ready"
