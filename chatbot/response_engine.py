
import json
import random
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from chatbot.gemini_service import generate_cyber_answer
from chatbot.phishing_detector import check_url
from chatbot.nlp_analysis import analyze_message


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

with open(
    PROJECT_DIR / "datasets" / "intents.json",
    encoding="utf-8",
) as f:
    intents_data = json.load(f)

with open(
    BASE_DIR / "knowledge_base.json",
    encoding="utf-8",
) as f:
    knowledge_data = json.load(f)


response_map = {
    item["tag"]: item["responses"]
    for item in knowledge_data["intents"]
}

knowledge_map = {
    item["tag"]: item
    for item in knowledge_data["intents"]
}


questions = []
tags = []

for intent in intents_data["intents"]:
    for pattern in intent["patterns"]:
        questions.append(pattern)
        tags.append(intent["tag"])


vectorizer = TfidfVectorizer(
    lowercase=True,
    ngram_range=(1, 2),
    strip_accents="unicode",
)

question_vectors = vectorizer.fit_transform(questions)


# ---------------------------------------------------------
# Small talk and follow-up phrases
# ---------------------------------------------------------

GREETINGS = {
    "hi",
    "hello",
    "hey",
    "namaste",
    "good morning",
    "good afternoon",
    "good evening",
}

THANKS_MESSAGES = {
    "thanks",
    "thank you",
    "thanks a lot",
    "thank you so much",
    "thx",
    "thanks thats helpful",
    "thank you thats helpful",
    "that is helpful",
    "thats helpful",
    "that was helpful",
    "thanks for your help",
    "thank you for your help",
    "much appreciated",
}

ACKNOWLEDGMENTS = {
    "okay",
    "ok",
    "got it",
    "understood",
    "makes sense",
}

AFFIRMATIVE_REPLIES = {
    "yes",
    "yeah",
    "yep",
    "sure",
    "yes please",
    "yes tell me",
    "tell me more",
    "go ahead",
    "please do",
}

FOLLOW_UP_PHRASES = (
    "what should i do",
    "what should i do now",
    "what if",
    "already shared",
    "already paid",
    "already clicked",
    "what about",
    "tell me more",
    "how can i prevent it",
    "how do i report it",
    "what happens next",
    "and then",
    "is it safe",
    "how to recover",
    "i already did",
    "how it happens",
    "how does it happen",
    "how does it work",
    "why does it happen",
    "explain more",
    "tell me how",
    "how can this happen",
    "how can it happen",
    "what are the signs",
    "how to prevent it",
    "how to stay safe",
    "how it works",
    "what happens if",
    "can you explain",
    "give me an example",
    "explain this",
    "what about that",
    "how to avoid it",
    "what next",
    "why is that",
)


# ---------------------------------------------------------
# Text helpers
# ---------------------------------------------------------

def normalize_text(text):
    """Lowercase text, remove punctuation, and normalize spaces."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text)


def extract_history_text(conversation_history):
    """Convert recent conversation history into readable messages."""
    if not isinstance(conversation_history, list):
        return []

    recent_messages = []

    for message in conversation_history[-8:]:
        if not isinstance(message, dict):
            continue

        role = message.get("role") or message.get("sender") or ""
        role = role.lower() if isinstance(role, str) else ""

        content = (
            message.get("content")
            or message.get("text")
            or message.get("message")
            or ""
        )

        if (
            role in ("user", "assistant", "bot")
            and isinstance(content, str)
            and content.strip()
        ):
            speaker = (
                "Assistant"
                if role in ("assistant", "bot")
                else "User"
            )

            recent_messages.append(
                f"{speaker}: {content.strip()[:1500]}"
            )

    return recent_messages


def get_previous_user_questions(history):
    """Get previous user messages from conversation history."""
    return [
        item[len("User: "):].strip()
        for item in history
        if isinstance(item, str) and item.startswith("User: ")
    ]


def match_intent(text):
    """Return the closest intent and its similarity score."""
    vector = vectorizer.transform([text])
    scores = cosine_similarity(
        vector,
        question_vectors,
    ).flatten()

    best_index = int(scores.argmax())

    return tags[best_index], float(scores[best_index])


# ---------------------------------------------------------
# URL detection and phishing report
# ---------------------------------------------------------

def find_url_in_message(text):
    """Find an explicit URL or domain supplied by the user."""
    pattern = (
        r"""(?:https?://|www\.)[^\s<>'"]+"""
        r"""|(?<![@\w])(?:[a-zA-Z0-9-]+\.)+"""
        r"""[a-zA-Z]{2,}(?:/[^\s<>'"]*)?"""
    )

    matches = re.findall(
        pattern,
        text,
        flags=re.IGNORECASE,
    )

    if not matches:
        return None

    candidate = matches[0].rstrip(".,;:!?)]}")

    if "." not in candidate or "@" in candidate:
        return None

    if candidate.lower().startswith("www."):
        candidate = "https://" + candidate
    elif not candidate.lower().startswith(
        ("http://", "https://")
    ):
        candidate = "https://" + candidate

    return candidate


def build_url_report(candidate_url, result):
    """Format phishing detector results as Markdown."""
    probability = result.get("phishing_probability")

    try:
        probability_percent = float(probability) * 100
    except (TypeError, ValueError):
        probability_percent = None

    probability_text = (
        f"{probability_percent:.1f}%"
        if probability_percent is not None
        else "unavailable"
    )

    return (
        "## URL Safety Check\n\n"
        f"- **URL:** {result.get('url', candidate_url)}\n"
        f"- **Assessment:** "
        f"{result.get('assessment', 'Assessment unavailable')}\n"
        f"- **Model-estimated phishing probability:** "
        f"{probability_text}\n\n"
        f"**Important:** "
        f"{result.get('warning', 'This automated result is not a guarantee of safety.')}\n\n"
        "**Safety steps**\n"
        "- Do not enter passwords, OTPs, or payment details "
        "on an unverified site.\n"
        "- Check the domain spelling and access services "
        "through their official app or a known address.\n"
        "- If the link seems suspicious, do not open it. "
        "Report it to the relevant service."
    )


# ---------------------------------------------------------
# Main chatbot response function
# ---------------------------------------------------------

def get_answer(user_message, conversation_history=None):
    """Generate a cybersecurity answer with conversation context."""

    if (
        not isinstance(user_message, str)
        or not user_message.strip()
    ):
        return "Please enter a question."

    cleaned = normalize_text(user_message)
    history = extract_history_text(conversation_history)

    # IMPORTANT:
    # Handle "yes" before generic acknowledgement replies.
    # Use the previous assistant message to understand the reply.
    if cleaned in AFFIRMATIVE_REPLIES and history:

        last_assistant_message = next(
            (
                item[len("Assistant: "):].strip()
                for item in reversed(history)
                if item.startswith("Assistant: ")
            ),
            "",
        )

        if last_assistant_message:
            conversation_text = "\n".join(history[-6:])

            follow_up_question = (
                f"Recent conversation:\n"
                f"{conversation_text}\n\n"
                f"The user's current reply is: {user_message}\n\n"
                "Understand this short affirmative reply using "
                "the previous assistant message.\n"
                "If the assistant offered to explain a topic or "
                "provide next steps, do that now.\n"
                "Stay on the same topic and answer directly.\n"
                "Do not give a generic list of cybersecurity topics.\n"
                "Do not ask the user to choose the topic again "
                "when the previous offer makes the topic clear."
            )

            return generate_cyber_answer(
                question=follow_up_question,
                context=(
                    "Category: cybersecurity awareness\n"
                    "Use the recent conversation to understand "
                    "and answer the implied follow-up."
                ),
            )

    # Handle greetings.
    if cleaned in GREETINGS:
        return random.choice(
            response_map.get(
                "greeting",
                ["Hello! How can I help you stay safe online?"],
            )
        )

    # Handle thank-you messages.
    if (
        cleaned in THANKS_MESSAGES
        or (
            cleaned.startswith(("thanks ", "thank you "))
            and any(
                phrase in cleaned
                for phrase in (
                    "helpful",
                    "that helped",
                    "for your help",
                )
            )
        )
    ):
        return (
            "You're welcome! Stay safe online. "
            "Feel free to ask if you need more cybersecurity help."
        )

    # Handle acknowledgements other than affirmative follow-ups.
    if cleaned in ACKNOWLEDGMENTS:
        return (
            "Glad that helped! Let me know if you have "
            "another cybersecurity question."
        )

    # Detect URLs and use the dedicated phishing detector.
    candidate_url = find_url_in_message(user_message)

    if candidate_url:
        result = check_url(candidate_url)

        if result.get("ok"):
            return build_url_report(candidate_url, result)

    # Analyze the message and identify its likely intent.
    message_analysis = analyze_message(user_message)

    previous_questions = get_previous_user_questions(history)
    best_tag, confidence = match_intent(user_message)

    is_follow_up = any(
        phrase in cleaned
        for phrase in FOLLOW_UP_PHRASES
    )

    words = cleaned.split()

    vague_references = {
        "it",
        "this",
        "that",
        "they",
        "them",
        "there",
    }

    short_follow_up = (
        len(words) <= 5
        and bool(set(words) & vague_references)
    )

    # Resolve contextual follow-ups to the previous user topic.
    if previous_questions and (
        is_follow_up or short_follow_up
    ):
        previous_tag, previous_confidence = match_intent(
            previous_questions[-1]
        )

        if previous_confidence >= 0.20:
            best_tag = previous_tag
            confidence = previous_confidence

    print(
        f"Question: {user_message} | "
        f"Matched tag: {best_tag} | "
        f"Score: {confidence:.3f} | "
        f"Follow-up: {is_follow_up or short_follow_up}"
    )

    if confidence < 0.20:
        return (
            "I'm not sure which topic you mean. Please tell me "
            "a little more about the situation, or ask about "
            "phishing, OTP fraud, job scams, UPI fraud, "
            "investment scams, or shopping scams."
        )

    knowledge = knowledge_map.get(best_tag)

    if not knowledge:
        return (
            "I don't have verified information for this topic yet."
        )

    context = "\n".join(
        knowledge.get("responses", [])
    )

    context += (
        "\n\nUser-message analysis (supporting signals only): "
        + json.dumps(
            message_analysis,
            ensure_ascii=False,
        )
        + "\nTreat sentiment as a rough estimate and entities "
        "as extracted text, not verified facts. "
        "Do not infer identity or intent from them."
    )

    instructions = """
Instructions:
- Answer the current question directly.
- Do not repeat the welcome message.
- Use conversation history to understand context and references.
- For a specific new question, answer the new topic.
- For follow-ups, answer the new question without repeating
  the entire previous answer.
- Use clear Markdown, short paragraphs, and numbered steps
  when useful.
- Put urgent actions first when the user may be at risk.
- Do not claim a URL, attachment, account, or website is safe
  based only on limited information.
- Explain that automated phishing scores are estimates,
  not guarantees.
- Do not invent facts, contact details, or reporting procedures.
- Keep responses focused and practical, usually around
  100-250 words.
- Clicking a suspicious link alone does not prove a device
  is infected.
- If a user entered a password, advise changing it from a
  trusted device and enabling multi-factor authentication.
- If banking details or an OTP were shared, advise contacting
  the bank immediately through an official channel.
- If money was stolen in India, advise contacting the bank
  and reporting promptly through 1930 or cybercrime.gov.in.
- Downloading a file alone does not prove infection.
  If it has not been opened, advise not opening it, deleting
  or quarantining it, and running an updated security scan.
"""

    if history:
        conversation_text = "\n".join(history[-6:])

        question_for_gemini = (
            f"Recent conversation:\n"
            f"{conversation_text}\n\n"
            f"Current user question:\n"
            f"{user_message}\n\n"
            f"{instructions}"
        )
    else:
        question_for_gemini = (
            f"Current user question:\n"
            f"{user_message}\n\n"
            f"{instructions}"
        )

    answer = generate_cyber_answer(
        question=question_for_gemini,
        context=f"Category: {best_tag}\n{context}",
    )

    if not isinstance(answer, str) or not answer.strip():
        return random.choice(
            knowledge["responses"]
        )

    if answer.startswith(
        "Gemini API key is not configured"
    ):
        return answer

    if answer.startswith(
        "Sorry, I couldn't generate an answer"
    ):
        return random.choice(
            knowledge["responses"]
        )

    return answer.strip()
