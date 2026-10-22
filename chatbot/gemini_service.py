
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

client = (
    genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=25000)
    )
    if api_key else None
)


def generate_cyber_answer(question, context):
    if client is None:
        return (
            "CyberSafe AI is temporarily unavailable.\n\n"
            "Please check the AI service configuration."
        )

    prompt = f"""
You are CyberSafe AI, a cybersecurity awareness assistant.
Answer the user's question accurately in simple, professional English.
Give practical safety steps and use headings or bullet points when useful.
Never claim a website is safe based only on its URL.
Treat general online safety questions as general cybersecurity questions,
not automatically as phishing questions.
Use conversation history for relevant follow-up questions.
Use the full recent conversation history to understand follow-up replies.

If the user says "yes", "yeah", "ok", or "sure", interpret it
using the previous assistant message.

If you previously offered to explain more about the current topic,
continue explaining that topic instead of asking the user to choose again.

If the previous message offered multiple specific options, ask which
option the user means.

Never treat a short reply as a new unrelated question.
Context:
{context}

Question:
{question}

Return a clear, helpful answer.
"""

    models = [
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
    ]

    for model in models:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )

            answer = getattr(response, "text", None)
            if answer and answer.strip():
                return answer.strip()

            print(f"Gemini returned an empty answer for {model}")

        except Exception as error:
            print(f"Gemini request failed for {model}: {error}")

    return (
        "CyberSafe AI — Temporary Service Issue\n\n"
        "The AI service is temporarily unavailable. Please try again "
        "shortly. Never share passwords, OTPs, or banking PINs."
    )
