
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

client = (
    genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=60000)
    )
    if api_key else None
)


def generate_cyber_answer(question, context):
    if client is None:
        return (
            "Configuration Error\n\n"
            "Gemini API key is not configured."
        )

    prompt = f"""
You are CyberSafe AI, a professional cybersecurity awareness assistant.

Provide accurate, helpful, well-structured answers about cybersecurity,
online scams, fraud prevention, and digital safety.

Use simple professional English, clear headings, short paragraphs,
numbered steps, and bullet points where appropriate.
Do not use raw Markdown symbols such as ###, **, or ---.
Use conversation history to answer follow-up questions.
For follow-ups, give only the relevant next actions.
Do not claim a website is safe based only on its URL.

For scam-related questions, cover warning signs, prevention,
actions to take if affected, and reporting options when relevant.
For general cybersecurity questions, use relevant headings.

Context:
{context}

Conversation and current question:
{question}

Return only the final answer in plain text.
"""

    models = [
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
    ]

    for model in models:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )

                if response.text and response.text.strip():
                    return response.text.strip()

                break

            except Exception as error:
                print(
                    f"Gemini error | model={model} "
                    f"| attempt={attempt + 1}: {error}"
                )

                message = str(error).lower()
                temporary = any(
                    word in message
                    for word in [
                        "503", "504", "429", "500", "502",
                        "unavailable", "deadline_exceeded",
                        "resource_exhausted", "timeout",
                        "timed out",
                    ]
                )

                if not temporary:
                    break

                if attempt == 0:
                    time.sleep(2)

    return (
        "CyberSafe AI — Temporary Service Issue\n\n"
        "The AI service is temporarily unavailable. Please try again "
        "shortly. Meanwhile, avoid suspicious links and never share "
        "your passwords, OTPs, or banking PINs."
    )
