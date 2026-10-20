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


# ---------------------------------------------------------------------------
# Small-talk detection (greetings, thanks, acknowledgements, goodbyes)
# ---------------------------------------------------------------------------
# NOTE: every phrase below is written in NORMALIZED form (lowercase, no
# punctuation) because messages are normalized before they are compared.

GREETINGS = {
    "hi",
    "hello",
    "hey",
    "hii",
    "hiii",
    "heyy",
    "namaste",
    "good morning",
    "good afternoon",
    "good evening",
    "hi there",
    "hello there",
    "hey there",
    "hi cybersafe",
    "hello cybersafe",
}

ACKNOWLEDGMENTS = {
    "okay",
    "ok",
    "okk",
    "k",
    "alright",
    "got it",
    "i got it",
    "understood",
    "i understand",
    "makes sense",
    "that makes sense",
    "i see",
    "cool",
    "great",
    "nice",
    "perfect",
    "sure",
    "fine",
    "noted",
}

GOODBYES = {
    "bye",
    "goodbye",
    "bye bye",
    "see you",
    "see you later",
    "take care",
    "good night",
    "talk to you later",
    "ttyl",
}

# Matches thanks / appreciation anywhere in a short message.
THANKS_PATTERN = re.compile(
    r"\b("
    r"thanks|thank you|thankyou|thank u|thx|tysm|ty|many thanks|"
    r"appreciate it|appreciate that|appreciate the help|"
    r"(that|this) (is|was|has been) (really |very |so )?"
    r"(helpful|useful|great|good|clear|informative)|"
    r"thats (really |very |so )?(helpful|useful|great|good|clear|informative)|"
    r"great help|good help|nice answer|good answer|great answer"
    r")\b"
)

# If any of these words appear, the user is asking something, not just thanking.
QUESTION_WORDS = {
    "what", "how", "why", "when", "where", "which", "who", "whom",
    "should", "could", "would", "can", "will", "does", "do", "did",
    "explain", "tell", "show", "give", "help me", "also", "another", "but",
}

THANKS_REPLIES = [
    "You're welcome! Stay safe online. Feel free to ask if you need more cybersecurity help.",
    "Happy to help! If you have another cybersecurity question, just ask.",
    "Glad that helped! Remember to stay alert for suspicious links and never share your OTP.",
    "Anytime! Stay cautious online, and ask me whenever you need more guidance.",
]

ACK_REPLIES = [
    "Glad that helped. Let me know if you have another cybersecurity question.",
    "Great! I'm here if you want to know more about staying safe online.",
    "Sounds good. Feel free to ask if anything else comes up.",
]

GOODBYE_REPLIES = [
    "Goodbye! Stay safe online.",
    "Take care! Remember: never share your OTP or passwords with anyone.",
    "See you later! Stay alert and stay secure.",
]

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


def normalize_text(text):
    """Lowercase, remove punctuation (including apostrophes) and extra spaces."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text)


def is_greeting(cleaned):
    return cleaned in GREETINGS


def is_thanks(cleaned, raw_message):
    """
    True only when the message is *just* thanks / appreciation.
    "Thanks, that's helpful!"            -> True
    "thank you so much"                  -> True
    "thanks! what about passwords?"      -> False (contains a new question)
    """
    if "?" in raw_message:
        return False

    words = cleaned.split()
    if not words or len(words) > 10:
        return False

    if not THANKS_PATTERN.search(cleaned):
        return False

    return not (set(words) & QUESTION_WORDS)


def is_acknowledgment(cleaned):
    return cleaned in ACKNOWLEDGMENTS


def is_goodbye(cleaned):
    return cleaned in GOODBYES


def get_small_talk_reply(user_message, cleaned):
    """Return a reply for greetings / thanks / acknowledgements / goodbyes, else None."""
    if is_greeting(cleaned):
        return random.choice(
            response_map.get(
                "greeting",
                ["Hello! How can I help you stay safe online?"],
            )
        )

    if is_thanks(cleaned, user_message):
        return random.choice(THANKS_REPLIES)

    if is_acknowledgment(cleaned):
        return random.choice(ACK_REPLIES)

    if is_goodbye(cleaned):
        return random.choice(GOODBYE_REPLIES)

    return None


# ---------------------------------------------------------------------------
# Conversation helpers
# ---------------------------------------------------------------------------

def extract_history_text(conversation_history):
    """Convert supported conversation-history formats to readable messages."""
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
            speaker = "Assistant" if role in ("assistant", "bot") else "User"
            recent_messages.append(f"{speaker}: {content.strip()[:1500]}")

    return recent_messages


def get_previous_user_questions(history):
    """
    Return earlier user messages that are real questions.
    Small talk (thanks, ok, hi, bye) is skipped so a later follow-up such as
    "what should I do now?" still refers to the last *real* topic.
    """
    questions_only = []

    for item in history:
        if not (isinstance(item, str) and item.startswith("User: ")):
            continue

        text = item[len("User: "):].strip()
        cleaned = normalize_text(text)

        if (
            is_greeting(cleaned)
            or is_thanks(cleaned, text)
            or is_acknowledgment(cleaned)
            or is_goodbye(cleaned)
        ):
            continue

        questions_only.append(text)

    return questions_only


def match_intent(text):
    """Return the closest intent and its cosine-similarity score."""
    vector = vectorizer.transform([text])
    scores = cosine_similarity(vector, question_vectors).flatten()
    best_index = int(scores.argmax())
    return tags[best_index], float(scores[best_index])


def find_url_in_message(text):
    """Find an explicit URL or domain supplied by the user."""
    pattern = r"""(?:https?://|www\.)[^\s<>'"]+|(?<![@\w])(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s<>'"]*)?"""
    matches = re.findall(pattern, text, flags=re.IGNORECASE)

    if not matches:
        return None

    candidate = matches[0].rstrip(".,;:!?)]}")
    if "." not in candidate or "@" in candidate:
        return None

    # Add a scheme for bare domains so the URL model receives a full URL.
    if candidate.lower().startswith("www."):
        candidate = "https://" + candidate
    elif not candidate.lower().startswith(("http://", "https://")):
        candidate = "https://" + candidate

    return candidate


def build_url_report(candidate_url, result):
    """Format the phishing-model result as Markdown."""
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
        f"- **Assessment:** {result.get('assessment', 'Assessment unavailable')}\n"
        f"- **Model-estimated phishing probability:** {probability_text}\n\n"
        f"**Important:** {result.get('warning', 'This automated result is not a guarantee of safety.')}\n\n"
        "**Safety steps**\n"
        "- Do not enter passwords, OTPs, or payment details on an unverified site.\n"
        "- Check the domain spelling and access services through their official app or a known address.\n"
        "- If the link seems suspicious, do not open it. Report it to the relevant service."
    )


COMMON_RULES = """
Instructions:
- Answer the current question directly. Do not start with "Hello" or "Hi", and do not repeat the welcome message.
- Use clear Markdown: a short heading when useful, short paragraphs, and numbered steps for actions.
- Put urgent actions first when the user may be at risk.
- Do not claim that a URL, attachment, account, or website is safe based only on limited information.
- Explain that automated phishing scores are estimates, not guarantees.
- Do not invent facts, contact details, or reporting procedures. If unsure, say so.
- Keep the response focused and practical, usually around 100-250 words unless more detail is needed.
- Keep advice proportionate to the user's described situation.
- If the user only clicked a suspicious link, explain that clicking alone does not prove the device is infected.
- If they entered a password, tell them to change it from a trusted device and enable multi-factor authentication.
- If they entered banking details or an OTP, tell them to contact their bank immediately through an official channel.
- Recommend disconnecting from the internet only when malware infection or ongoing suspicious activity is suspected.
- If a suspicious file was downloaded but not opened, advise not to open it, to delete or quarantine it, and to run an updated security scan. Do not assume the device is infected.
- Format numbered lists using sequential Markdown numbering: 1., 2., 3., 4.
- Never restart numbering at 1 for every list item.
- Do not mix numbered-list styles such as "1." and "1)".
- Use bullet points when the order of actions does not matter.
- Keep follow-up answers concise and avoid repeating previous advice.
"""

FOLLOW_UP_RULES = """
- Use the history only to understand context and resolve references such as "it", "this", or "that".
- For a specific new question, answer the new topic rather than continuing an unrelated old topic.
- For follow-up questions, answer only the new part; do not repeat the full previous answer.
"""


def build_prompt(user_message, history):
    if history:
        conversation_text = "\n".join(history[-6:])
        return (
            f"Recent conversation:\n{conversation_text}\n\n"
            f"Current user question:\n{user_message}\n"
            f"{COMMON_RULES}{FOLLOW_UP_RULES}"
        )

    return (
        f"Current user question:\n{user_message}\n"
        f"{COMMON_RULES}"
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def get_answer(user_message, conversation_history=None):
    """Generate a concise, well-formatted cybersecurity answer."""
    if not isinstance(user_message, str) or not user_message.strip():
        return "Please enter a question."

    cleaned = normalize_text(user_message)
    history = extract_history_text(conversation_history)

    # 1) Small talk first: greetings, thanks, acknowledgements, goodbyes.
    small_talk = get_small_talk_reply(user_message, cleaned)
    if small_talk:
        return small_talk

    # 2) Explicit URL/domain -> dedicated phishing model.
    #    A model score is a risk signal, not proof that a site is safe or malicious.
    candidate_url = find_url_in_message(user_message)
    if candidate_url:
        result = check_url(candidate_url)
        if result.get("ok"):
            return build_url_report(candidate_url, result)

    # 3) Intent matching with follow-up resolution.
    message_analysis = analyze_message(user_message)
    previous_questions = get_previous_user_questions(history)
    best_tag, confidence = match_intent(user_message)

    is_follow_up = any(phrase in cleaned for phrase in FOLLOW_UP_PHRASES)
    words = cleaned.split()
    vague_references = {"it", "this", "that", "they", "them", "there"}

    short_follow_up = (
        len(words) <= 5 and bool(set(words) & vague_references)
    )

    if previous_questions and (is_follow_up or short_follow_up):
        previous_question = previous_questions[-1]
        previous_tag, previous_confidence = match_intent(previous_question)

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
            "I'm not sure which topic you mean. Please tell me a little more "
            "about the situation, or ask about phishing, OTP fraud, job scams, "
            "UPI fraud, investment scams, or shopping scams."
        )

    knowledge = knowledge_map.get(best_tag)
    if not knowledge:
        return "I don't have verified information for this topic yet."

    context = "\n".join(knowledge.get("responses", []))
    context += (
        "\n\nUser-message analysis (supporting signals only): "
        + json.dumps(message_analysis, ensure_ascii=False)
        + "\nTreat sentiment as a rough estimate and entities as extracted text, "
        "not verified facts. Do not infer identity or intent from them."
    )

    answer = generate_cyber_answer(
        question=build_prompt(user_message, history),
        context=f"Category: {best_tag}\n{context}",
    )

    if not isinstance(answer, str) or not answer.strip():
        return random.choice(knowledge["responses"])

    if answer.startswith("Gemini API key is not configured"):
        return answer

    if answer.startswith("Sorry, I couldn't generate an answer"):
        return random.choice(knowledge["responses"])

    return answer.strip()