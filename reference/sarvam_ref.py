from sarvamai import SarvamAI
import os
from dotenv import load_dotenv

load_dotenv(override=True)

client = SarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))

with open("record_out.wav", "rb") as f:
    response = client.speech_to_text.transcribe(
        file=f,
        model="saaras:v4",
        language_code="gu-IN",
        mode="transcribe",
    )

print(response)
# print(response.transcript)

# for word in response.words:
#     print(f"[{word.start:.2f}s] {word.text}")