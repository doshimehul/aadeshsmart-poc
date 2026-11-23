from typing import Literal, Protocol

from pydantic import BaseModel, Field

from app.core.config import Settings


class DonationExtraction(BaseModel):
    name: str = Field(min_length=1, description="The donor's name in Gujarati")
    amount: int = Field(strict=True, description="Donation amount as an integer")
    amount_type: Literal["rupees", "man"]
    event: str = Field(min_length=1, description="The seva or event in Gujarati")


class TranscriptionProvider(Protocol):
    def transcribe(self, audio_path: str) -> str: ...


class ExtractionProvider(Protocol):
    def extract(self, transcript: str) -> DonationExtraction: ...


class MockTranscriptionProvider:
    def transcribe(self, audio_path: str) -> str:
        return "માતુ શ્રી નિર્મળા બેન દેવચંદ દોશી તરફથી એક હજાર એક મણ ઘીનું દાન."


class SarvamTranscriptionProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def transcribe(self, audio_path: str) -> str:
        if not self.settings.sarvam_api_key:
            raise RuntimeError("Sarvam live mode requires SARVAM_API_KEY")
        try:
            from sarvamai import SarvamAI

            client = SarvamAI(
                api_subscription_key=self.settings.sarvam_api_key,
                timeout=self.settings.sarvam_timeout_seconds,
            )
            with open(audio_path, "rb") as audio:
                response = client.speech_to_text.transcribe(
                    file=audio, model="saaras:v4", language_code="gu-IN", mode="transcribe",
                )
            transcript = getattr(response, "transcript", None)
            if not isinstance(transcript, str) or not transcript.strip():
                raise ValueError("Sarvam returned an empty transcription")
            return transcript
        except Exception as exc:
            raise RuntimeError(f"Sarvam transcription failed ({type(exc).__name__})") from None


class MockExtractionProvider:
    def extract(self, transcript: str) -> DonationExtraction:
        return DonationExtraction(name="નિર્મળા બેન દેવચંદ દોશી", amount=1001, amount_type="man", event="ઘીનું દાન")


class GeminiExtractionProvider:
    INSTRUCTIONS = """You are an expert in Gujarati. Parse speech-to-text announcements of donations made at a sangh event. Convert spoken amounts into integers. amount_type must be rupees or man. Keep the donor name and seva/event in Gujarati."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def extract(self, transcript: str) -> DonationExtraction:
        if not self.settings.google_api_key:
            raise RuntimeError("Gemini live mode requires GOOGLE_API_KEY")
        try:
            from agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
            from openai import AsyncOpenAI

            set_tracing_disabled(True)
            client = AsyncOpenAI(
                api_key=self.settings.google_api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
            model = OpenAIChatCompletionsModel(model=self.settings.gemini_model, openai_client=client)
            agent = Agent(name="Gujarati donation parser", instructions=self.INSTRUCTIONS,
                          model=model, output_type=DonationExtraction)
            result = Runner.run_sync(agent, f"Parse this Gujarati donation announcement:\n{transcript}")
            parsed = result.final_output
            if isinstance(parsed, DonationExtraction):
                return parsed
            return DonationExtraction.model_validate(parsed)
        except Exception as exc:
            raise RuntimeError(f"Gemini extraction failed ({type(exc).__name__})") from None
