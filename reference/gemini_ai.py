import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, set_tracing_disabled
from pydantic import BaseModel, Field

load_dotenv(override=True)
set_tracing_disabled(True)

google_api_key = os.getenv("GOOGLE_API_KEY")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-3.8-flash"

instructions = """
You are an expert in Gujarati. Parse speech-to-text announcements of donations
made at a sangh event. Convert spoken amounts into integers. Amount type is
either "rupees" or "man". Keep the donor name and the seva or event in Gujarati.
"""


class GujaratiParser(BaseModel):
    name: str = Field(description="The donor's name")
    amount: int = Field(description="The donation amount as an integer")
    amount_type: str = Field(description="Either rupees or man")
    event: str = Field(description="The seva or event the donation is for")


def build_task(text: str) -> str:
    return f"""
Parse the text and extract the donation. The text is Gujarati from a speech-to-text
module. The speaker announces a donation amount in words, an amount type of either
rupees or man, the donor name, and the event or work the donation is for.

Example:
સિંહ ને માથે લઈને ચાડવાનું ઘી એક હઝાર ને એક મણ માતુ શ્રી નિર્મળા બેન દેવચંદ દોશી

Text:
{text}
"""


def main() -> None:
    if not google_api_key:
        raise SystemExit(
            "GOOGLE_API_KEY is missing. Create a .env file with GOOGLE_API_KEY=... and run again."
        )

    text = input("Enter the Gujarati announcement: ").strip()
    if not text:
        raise SystemExit("No text entered.")
    gemini_client = AsyncOpenAI(api_key=google_api_key, base_url=GEMINI_BASE_URL)
    gemini_model = OpenAIChatCompletionsModel(model=GEMINI_MODEL, openai_client=gemini_client)

    agent = Agent(
        name="Gujarati donation parser",
        instructions=instructions,
        model=gemini_model,
        output_type=GujaratiParser,
    )

    result = Runner.run_sync(agent, build_task(text))
    parsed = result.final_output
    print(parsed.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
