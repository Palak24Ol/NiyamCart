import base64
from pathlib import Path

from app.agent_schemas import AgentRunResponse
from app.main import create_app
from app.sarvam_service import PreparedText, SarvamError
from fastapi.testclient import TestClient


class FakeSarvam:
    def __init__(self) -> None:
        self.transcribed: tuple[bytes, str] | None = None
        self.prepared: tuple[str, str | None, str | None] | None = None
        self.synthesized: tuple[str, str] | None = None

    def transcribe(self, audio: bytes, content_type: str) -> PreparedText:
        self.transcribed = (audio, content_type)
        return PreparedText(
            "मुझे नीली चादर चाहिए",
            "I want a blue bedsheet",
            "hi-IN",
            "Deva",
            0.98,
        )

    def prepare_text(
        self,
        text: str,
        language_code: str | None = None,
        script_code: str | None = None,
    ) -> PreparedText:
        self.prepared = (text, language_code, script_code)
        return PreparedText(text, "blue bedsheet under 300 rupees", "hi-IN", "Deva")

    def localize(self, text: str, language_code: str, script_code: str | None) -> str:
        assert text == "I found a blue bedsheet under your budget."
        assert (language_code, script_code) == ("hi-IN", "Deva")
        return "मुझे आपके बजट में एक नीली चादर मिली।"

    def synthesize(self, text: str, language_code: str) -> tuple[str, str]:
        self.synthesized = (text, language_code)
        return base64.b64encode(b"RIFF-test-wave").decode(), "audio/wav"


def fake_agent_response() -> AgentRunResponse:
    return AgentRunResponse(
        session_id="voice-session",
        status="completed",
        answer="I found a blue bedsheet under your budget.",
        proposed_cart_id=None,
        step_count=2,
        revision_count=0,
        estimated_cost_microusd=12,
        recommended_product_ids=["P-301"],
    )


def test_transcribe_endpoint_preserves_language_metadata(tmp_path: Path) -> None:
    provider = FakeSarvam()
    app = create_app(f"sqlite:///{tmp_path / 'voice.db'}", sarvam_provider=provider)

    with TestClient(app) as client:
        response = client.post(
            "/api/voice/transcribe",
            content=b"webm-audio",
            headers={"content-type": "audio/webm;codecs=opus"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "transcript": "मुझे नीली चादर चाहिए",
        "normalized_text": "I want a blue bedsheet",
        "language_code": "hi-IN",
        "script_code": "Deva",
        "language_probability": 0.98,
    }
    assert provider.transcribed == (b"webm-audio", "audio/webm;codecs=opus")


def test_agent_localizes_and_speaks_without_changing_tool_query(
    tmp_path: Path,
    monkeypatch,
) -> None:
    provider = FakeSarvam()
    captured: dict[str, object] = {}

    def fake_run_agent(session, message: str, **kwargs) -> AgentRunResponse:
        captured["message"] = message
        captured["original_message"] = kwargs["original_message"]
        captured["language_code"] = kwargs["language_code"]
        return fake_agent_response()

    monkeypatch.setattr("app.main.run_agent", fake_run_agent)
    app = create_app(f"sqlite:///{tmp_path / 'agent-voice.db'}", sarvam_provider=provider)

    with TestClient(app) as client:
        response = client.post(
            "/api/agent/sessions",
            json={"message": "मुझे 300 रुपये से कम की नीली चादर चाहिए", "synthesize_audio": True},
        )

    payload = response.json()
    assert response.status_code == 201
    assert captured == {
        "message": "blue bedsheet under 300 rupees",
        "original_message": "मुझे 300 रुपये से कम की नीली चादर चाहिए",
        "language_code": "hi-IN",
    }
    assert payload["answer"] == "मुझे आपके बजट में एक नीली चादर मिली।"
    assert payload["language_code"] == "hi-IN"
    assert payload["localization_status"] == "localized"
    assert payload["voice_status"] == "ready"
    assert base64.b64decode(payload["audio_base64"]) == b"RIFF-test-wave"
    assert provider.synthesized == (payload["answer"], "hi-IN")


class FailingTranscriber(FakeSarvam):
    def transcribe(self, audio: bytes, content_type: str) -> PreparedText:
        raise SarvamError("SARVAM_UNAVAILABLE", "Voice service is temporarily unavailable.")


def test_voice_failure_is_clear_and_bounded(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{tmp_path / 'failed-voice.db'}",
        sarvam_provider=FailingTranscriber(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/voice/transcribe",
            content=b"webm-audio",
            headers={"content-type": "audio/webm"},
        )

    assert response.status_code == 502
    assert response.json() == {
        "error": "SARVAM_UNAVAILABLE",
        "message": "Voice service is temporarily unavailable.",
    }
