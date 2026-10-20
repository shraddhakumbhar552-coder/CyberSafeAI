"""Lightweight sentiment analysis and cybersecurity-focused entity extraction.

If spaCy and its English model are installed, generic named entities are added.
Regex extraction remains available without that optional model.
"""
from __future__ import annotations

import re

POSITIVE = {
    "good", "great", "excellent", "safe", "thanks", "thank", "helpful",
    "happy", "love", "secure", "resolved", "recovered", "okay", "ok",
}
NEGATIVE = {
    "bad", "scam", "fraud", "phishing", "hacked", "hack", "stolen",
    "lost", "angry", "sad", "afraid", "scared", "worried", "urgent",
    "blackmail", "threat", "suspicious", "unsafe", "malware", "virus",
    "stolen", "blocked", "failed", "problem", "panic",
}
NEGATIONS = {"not", "never", "no", "isn't", "wasn't", "can't", "cannot", "dont", "don't"}

_SPACY_NLP = None
_SPACY_ATTEMPTED = False

PATTERNS = {
    "URL": re.compile(r"\b(?:https?://|www\.)[^\s<>\"]+", re.I),
    "DOMAIN": re.compile(r"(?<![@\w])\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>\"]*)?", re.I),
    "EMAIL": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "IP_ADDRESS": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "PHONE_NUMBER": re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)"),
    "OTP_REFERENCE": re.compile(r"\b(?:OTP|one[- ]time password|verification code)\b", re.I),
    "FINANCIAL_TERM": re.compile(r"\b(?:UPI|Paytm|PhonePe|Google Pay|GPay|bank account|credit card|debit card|wallet)\b", re.I),
    "ORGANIZATION": re.compile(r"\b(?:Google|Microsoft|Apple|Amazon|PayPal|Paytm|PhonePe|WhatsApp|Instagram|Facebook|Telegram|RBI|NPCI|CERT-In)\b", re.I),
}


def analyze_sentiment(text: str) -> dict:
    """Small, explainable lexicon sentiment baseline; not a clinical emotion detector."""
    words = re.findall(r"[a-z']+", text.lower())
    positive = 0
    negative = 0
    for index, word in enumerate(words):
        negated = index > 0 and words[index - 1] in NEGATIONS
        if word in POSITIVE:
            negative += int(negated)
            positive += int(not negated)
        elif word in NEGATIVE:
            positive += int(negated)
            negative += int(not negated)
    total = positive + negative
    score = (positive - negative) / total if total else 0.0
    label = "positive" if score > 0.15 else "negative" if score < -0.15 else "neutral"
    return {
        "label": label,
        "score": round(score, 3),
        "positive_terms": positive,
        "negative_terms": negative,
        "method": "lexicon_baseline",
    }


def extract_entities(text: str) -> list[dict]:
    """Extract cybersecurity-relevant entities and optional spaCy entities."""
    entities = []
    seen = set()
    for label, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            value = match.group(0).rstrip(".,;:)")
            key = (label, value.lower())
            if value and key not in seen:
                entities.append({"text": value, "label": label})
                seen.add(key)

    # Generic NER is optional; the regex recognizers above work without a model.
    global _SPACY_NLP, _SPACY_ATTEMPTED
    if not _SPACY_ATTEMPTED:
        _SPACY_ATTEMPTED = True
        try:
            import spacy
            _SPACY_NLP = spacy.load("en_core_web_sm")
        except (ImportError, OSError):
            _SPACY_NLP = None
    if _SPACY_NLP is not None:
        for ent in _SPACY_NLP(text[:5000]).ents:
            if ent.label_ in {"PERSON", "ORG", "GPE", "LOC", "DATE", "MONEY"}:
                key = (ent.label_, ent.text.lower())
                if key not in seen:
                    entities.append({"text": ent.text, "label": ent.label_})
                    seen.add(key)

    return entities


def analyze_message(text: str) -> dict:
    return {
        "sentiment": analyze_sentiment(text),
        "entities": extract_entities(text),
    }
