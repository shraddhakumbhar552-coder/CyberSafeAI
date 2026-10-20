"""Train and evaluate the phishing URL classifier using the bundled CSV dataset.

Run from the project root:
    python scripts/train_phishing_model.py
Label convention in the provided data: 1 = phishing, 0 = legitimate.
"""
from pathlib import Path
import json
import sys

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, roc_auc_score
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "datasets" / "phishing_features.csv"
MODEL_PATH = ROOT / "models" / "phishing_url_model.joblib"
METRICS_PATH = ROOT / "models" / "phishing_model_metrics.json"
FEATURES = [
    "url_length", "num_dots", "has_https", "has_ip", "num_subdirs",
    "num_params", "suspicious_words", "tld", "special_char_count",
    "digits_count", "entropy",
]
LABEL = "label"


def main():
    if not DATA_PATH.exists():
        raise SystemExit(f"Dataset not found: {DATA_PATH}")
    data = pd.read_csv(DATA_PATH)
    missing = set(FEATURES + [LABEL]) - set(data.columns)
    if missing:
        raise SystemExit(f"Dataset is missing required columns: {sorted(missing)}")
    data = data[FEATURES + [LABEL]].dropna()
    data["tld"] = data["tld"].astype(str).str.lower()
    X, y = data[FEATURES], data[LABEL].astype(int)

    if set(y.unique()) != {0, 1}:
        raise SystemExit("Expected binary labels 0 and 1; check dataset label convention.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    numeric = [column for column in FEATURES if column != "tld"]
    preprocess = ColumnTransformer([
        ("tld", OneHotEncoder(handle_unknown="ignore"), ["tld"]),
        ("numeric", StandardScaler(), numeric),
    ])
    classifier = Pipeline([
        ("preprocess", preprocess),
        ("model", LogisticRegression(
            class_weight="balanced", max_iter=500, solver="liblinear",
            random_state=42
        )),
    ])
    classifier.fit(X_train, y_train)
    predictions = classifier.predict(X_test)
    probabilities = classifier.predict_proba(X_test)[:, 1]
    metrics = {
        "dataset": DATA_PATH.name,
        "rows_used": int(len(data)),
        "label_convention": {"0": "legitimate", "1": "phishing"},
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "class_counts": {str(int(k)): int(v) for k, v in y.value_counts().items()},
        "accuracy": float(accuracy_score(y_test, predictions)),
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "confusion_matrix_labels_0_then_1": confusion_matrix(
            y_test, predictions, labels=[0, 1]
        ).tolist(),
        "classification_report": classification_report(
            y_test, predictions, labels=[0, 1],
            target_names=["legitimate", "phishing"], output_dict=True,
            zero_division=0
        ),
        "note": "The supplied dataset is highly imbalanced. Metrics are a held-out split of this dataset, not a guarantee of real-world performance.",
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(classifier, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({
        "model": str(MODEL_PATH),
        "metrics_file": str(METRICS_PATH),
        "rows_used": metrics["rows_used"],
        "class_counts": metrics["class_counts"],
        "accuracy": round(metrics["accuracy"], 4),
        "roc_auc": round(metrics["roc_auc"], 4),
        "confusion_matrix": metrics["confusion_matrix_labels_0_then_1"],
    }, indent=2))


if __name__ == "__main__":
    main()
