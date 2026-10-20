"""Feature extraction and inference for the CyberSafe AI phishing URL model."""
from __future__ import annotations

import ipaddress
import math
import re
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import joblib

PROJECT_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_DIR / "models" / "phishing_url_model.joblib"
MODEL = None
MODEL_LOAD_ERROR = None

SUSPICIOUS_TERMS = (
    "login", "log-in", "signin", "sign-in", "verify", "verification",
    "account", "update", "secure", "security", "bank", "confirm",
    "password", "wallet", "billing", "payment", "recover", "support",
    "authenticate", "webscr", "bonus", "prize", "gift", "free",
    "crypto", "metamask", "paypal", "credential", "otp",
)
SPECIAL_RE = re.compile(r"[@!#$%^&*()+=\[\]{};,'\"<>?\\|~`]")


def _normalize_url(value: str) -> str:
    value = value.strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value):
        value = "http://" + value
    return value


def extract_url_features(url: str) -> dict:
    """Extract the feature columns used to train the supplied CSV model."""
    normalized = _normalize_url(url)
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower().rstrip(".")
    try:
        ipaddress.ip_address(host)
        has_ip = 1
    except ValueError:
        has_ip = 0

    path = parsed.path or ""
    query = parsed.query or ""
    tld = host.rsplit(".", 1)[-1] if "." in host else (host or "unknown")
    text_lower = normalized.lower()
    entropy_counts = Counter(normalized)
    total = max(len(normalized), 1)
    entropy = -sum((count / total) * math.log2(count / total)
                   for count in entropy_counts.values())
    suspicious_count = sum(text_lower.count(term) for term in SUSPICIOUS_TERMS)

    # These calculations mirror the columns available in the supplied dataset.
    return {
        "url_length": len(normalized),
        "num_dots": normalized.count("."),
        "has_https": int(parsed.scheme.lower() == "https"),
        "has_ip": has_ip,
        "num_subdirs": normalized.count("/"),
        "num_params": len(parse_qs(query, keep_blank_values=True)),
        "suspicious_words": suspicious_count,
        "tld": tld,
        "special_char_count": len(SPECIAL_RE.findall(normalized)),
        "digits_count": sum(ch.isdigit() for ch in normalized),
        "entropy": entropy,
    }


def _get_model():
    global MODEL, MODEL_LOAD_ERROR
    if MODEL is not None:
        return MODEL
    if MODEL_LOAD_ERROR:
        return None
    try:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")
        MODEL = joblib.load(MODEL_PATH)
        return MODEL
    except Exception as exc:
        MODEL_LOAD_ERROR = str(exc)
        return None


def check_url(url: str) -> dict:
    """Return a model assessment. This is a risk signal, not a safety guarantee."""
    if not isinstance(url, str) or not url.strip():
        return {"ok": False, "error": "Enter a URL to check."}
    if len(url) > 2048:
        return {"ok": False, "error": "URL is too long (maximum 2048 characters)."}

    candidate = url.strip()
    if any(ch.isspace() for ch in candidate):
        return {"ok": False, "error": "Enter one URL without spaces."}

    parsed = urlparse(_normalize_url(candidate))
    if not parsed.hostname or "." not in parsed.hostname:
        return {"ok": False, "error": "Enter a valid domain or URL."}

    model = _get_model()
    if model is None:
        return {
            "ok": False,
            "error": "The phishing detection model is not available. Run the training script and check the model file.",
        }

    import pandas as pd
    features = extract_url_features(candidate)
    frame = pd.DataFrame([features])
    probability = float(model.predict_proba(frame)[0][1])
    label = int(model.predict(frame)[0])
    is_phishing = label == 1
    return {
        "ok": True,
        "url": candidate,
        "label": "likely_phishing" if is_phishing else "likely_legitimate",
        "assessment": "Likely suspicious / phishing" if is_phishing else "No obvious phishing signal detected",
        "phishing_probability": round(probability, 4),
        "confidence_percent": round((probability if is_phishing else 1 - probability) * 100, 1),
        "warning": "This is an automated model estimate, not proof that a site is malicious or safe. Do not enter passwords, OTPs, or payment details unless you independently verify the domain.",
    }
