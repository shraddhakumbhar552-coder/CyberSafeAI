# CyberSafe AI — Dynamic Cybersecurity Chatbot

A Flask-based cybersecurity awareness chatbot with Gemini-generated answers, TF-IDF intent matching, MySQL conversation history, sentiment analysis, cybersecurity-focused entity extraction, and a trained phishing-URL classifier.

## Features in this package

- **Generative AI:** Google Gemini API integration (`chatbot/gemini_service.py`).
- **Intent matching:** TF-IDF and cosine similarity over `datasets/intents.json`.
- **Conversation history:** user-owned chat sessions/messages stored in MySQL.
- **Phishing URL classifier:** scikit-learn Logistic Regression model trained on the bundled `datasets/phishing_features.csv`. The chat checks a URL/domain included in a message. Authenticated clients can also call `POST /api/check-url` with `{"url":"https://example.com"}`.
- **Sentiment analysis:** a small, explainable lexicon baseline (positive/negative/neutral). It is not a deep-learning emotion detector.
- **Entity extraction / NER:** built-in regex extraction for URLs/domains, email addresses, IP addresses, phone-like numbers, OTP references, financial terms, and common organizations. Optional spaCy integration adds general entities when its English model is installed.
- **User account features:** registration, login, profile settings and password change endpoints.
- **Basic analytics:** per-user conversation and bot-response counts.

## Important model limitations

The supplied CSV has a highly imbalanced label distribution (approximately 159,243 label-1 rows and 820 label-0 rows). In this dataset, `1` is treated as phishing and `0` as legitimate based on the examples. A held-out split is recorded in `models/phishing_model_metrics.json`; the metrics are not a guarantee of real-world performance. False positives and false negatives are possible. The model is a feature-based estimate, not a live reputation service, and does not visit or verify the target site. Never treat a model prediction as proof that a URL is safe.

The sentiment module is a rule/lexicon baseline. Entity extraction is cybersecurity-focused and regex-based by default, not a full general-purpose NER model. Optional spaCy support can be enabled below.

## Setup

### 1. Requirements

- Python 3.10+ recommended
- MySQL 8+ (or compatible MySQL server)
- A Gemini API key

### 2. Create an environment and install packages

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

If `mysqlclient` fails to install on your platform, install the required MySQL client development/build tools for your operating system, then retry.

### 3. Configure environment variables

Copy `.env.example` to `.env`, then set your own values:

```bash
# Generate a strong Flask secret:
python -c "import secrets; print(secrets.token_hex(32))"
```

Put the generated value in `FLASK_SECRET_KEY`, and put your Gemini API key in `GEMINI_API_KEY`. Set the MySQL credentials for your local server. **Never commit or share `.env`; it is excluded from the ZIP and `.gitignore`.**

### 4. Create the database

Run from the project root:

```bash
mysql -u root -p < database/schema.sql
```

The schema creates `cybersafe_ai`, `users`, `chat_sessions`, and `chat_messages`. Set `MYSQL_USER` and `MYSQL_PASSWORD` in `.env` to a database account that can access this database and create/alter chat tables if needed. The app initializes the chat tables on its first request, but the provided schema creates them up front.

### 5. Start the app

```bash
python app.py
```

Open `http://127.0.0.1:5000`, register an account, and start chatting.

## Phishing model

A trained model artifact is included at `models/phishing_url_model.joblib`, so normal startup does not need to retrain it.

To reproduce training and evaluation from the included CSV:

```bash
python scripts/train_phishing_model.py
```

This regenerates the model and `models/phishing_model_metrics.json`. Training uses a stratified 80/20 split, a `ColumnTransformer` for numeric features and TLD, and class-weighted Logistic Regression.

## Optional general-purpose NER

The built-in cybersecurity entity extraction works without spaCy. For additional general entities (PERSON, ORG, GPE, LOC, DATE, MONEY), install the optional dependency and model:

```bash
pip install -r requirements-ner.txt
python -m spacy download en_core_web_sm
```

Restart the app after installation.

## API notes

- `POST /api/chat` (authenticated): `{"message":"Is https://example.com safe?","history":[],"chat_id":null}`. Returns the answer, chat ID, and sentiment/entity analysis.
- `POST /api/check-url` (authenticated): `{"url":"https://example.com"}`. Returns model assessment and estimated phishing probability.
- `GET /api/analytics` (authenticated): basic per-user conversation and response counts.

The UI uses the existing frontend. URL checking can be triggered by asking about a URL in chat; the endpoint is also available to future frontend integrations.

## Tests

Run:

```bash
python -m unittest discover -s tests -v
```

## Deployment/security checklist

- Use HTTPS and set `COOKIE_SECURE=true` when deployed behind HTTPS.
- Use a strong, private `FLASK_SECRET_KEY`.
- Keep API keys and database passwords in environment variables, never in source control.
- Use a production WSGI server (for example Gunicorn on supported platforms); do not enable Flask debug mode in production.
- Add CSRF protection for browser form/API actions before public production deployment.
- Review model metrics on a separate, representative dataset before relying on phishing predictions.
