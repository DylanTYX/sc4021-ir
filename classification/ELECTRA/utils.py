"""Shared utilities — SC4021 Group 27 BERTweet Classification Pipeline."""

import re
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

# ── Label maps ────────────────────────────────────────────────────────────────

LABEL2ID = {"Negative": 0, "Neutral": 1, "Positive": 2}
ID2LABEL = {0: "Negative", 1: "Neutral", 2: "Positive"}

LABEL_NORMALISE = {
    "positive": "Positive", "pos": "Positive",  "1":  "Positive",
    "negative": "Negative", "neg": "Negative",  "-1": "Negative",
    "neutral":  "Neutral",  "neu": "Neutral",   "0":  "Neutral",
}

# ── Singapore political entities ──────────────────────────────────────────────

PAP_FIGURES = [
    "Lee Hsien Loong", "Lee Kuan Yew", "Lawrence Wong",
    "Tharman Shanmugaratnam", "Vivian Balakrishnan", "Chan Chun Sing",
    "Ong Ye Kung", "Desmond Lee", "Ng Eng Hen", "Heng Swee Keat",
    "Josephine Teo", "Grace Fu",
]

WP_FIGURES = [
    "Pritam Singh", "Sylvia Lim", "Leon Perera", "He Ting Ru",
    "Louis Chua", "Gerald Giam", "Faisal Manap", "Jamus Lim",
    "Nicole Seah", "Png Eng Huat", "Raeesah Khan",
]

OTHER_FIGURES = [
    "Tan Cheng Bock", "Chee Soon Juan", "Paul Tambyah", "Leong Mun Wai",
]

PARTIES = ["PAP", "WP", "PSP", "SDP", "RDU", "PAR", "SPP", "SDA"]

# ── Emoji support (optional) ──────────────────────────────────────────────────

try:
    import emoji as _emoji_lib
    _EMOJI_OK = True
except ImportError:
    _EMOJI_OK = False


# ── Text normalisation ────────────────────────────────────────────────────────

def normalise_text(text: str) -> str:
    """BERTweet-standard microtext normalisation."""
    if not isinstance(text, str):
        return ""
    # 1. HTML entities
    text = (text
            .replace("&amp;",  "&")
            .replace("&lt;",   "<")
            .replace("&gt;",   ">")
            .replace("&quot;", '"')
            .replace("&#39;",  "'")
            .replace("&nbsp;", " "))
    # 2. Reddit markdown
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)
    text = re.sub(r"(.+?)",            r"\1", text)
    text = re.sub(r"^>.*$", "",            text,  flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # 3. Emojis → text tokens
    if _EMOJI_OK:
        text = _emoji_lib.demojize(text, delimiters=(" emoji_", " "))
    # 4. URLs
    text = re.sub(r"http\S+|www\.\S+", "HTTPURL", text)
    # 5. @mentions
    text = re.sub(r"@\w+", "@USER", text)
    # 6. Hashtags (#SGPolitics → SGPolitics)
    text = re.sub(r"#(\w+)", r"\1", text)
    # 7. Collapse repeated characters (≥3 → 2)
    text = re.sub(r"(.)\1{2,}", r"\1\1", text)
    # 8. Normalise whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalise_label(raw) -> str:
    """Standardise values from manual_labelling column."""
    if not isinstance(raw, str):
        return "Neutral"
    return LABEL_NORMALISE.get(raw.strip().lower(), raw.strip().capitalize())


# ── Entity extraction ─────────────────────────────────────────────────────────

def extract_party(text: str) -> str:
    """Return comma-separated list of party acronyms mentioned in text."""
    found = [p for p in PARTIES if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", text)]
    return ", ".join(found) if found else "None"


def extract_person(text: str) -> str:
    """Return comma-separated list of political figures mentioned in text."""
    found = []
    for name in PAP_FIGURES:
        if name in text:
            found.append(f"{name} (PAP)")
    for name in WP_FIGURES:
        if name in text:
            found.append(f"{name} (WP)")
    for name in OTHER_FIGURES:
        if name in text:
            found.append(f"{name} (Other)")
    return ", ".join(found) if found else "None"


# ── Evaluation metrics ────────────────────────────────────────────────────────
def compute_metrics(y_true, y_pred, labels=None) -> dict:
    """Return accuracy, macro/weighted F1, per-class metrics, confusion matrix."""
    if labels is None:
        labels = sorted(set(y_true))
    report = classification_report(
        y_true, y_pred, labels=labels, output_dict=True, zero_division=0
    )
    return {
        "accuracy":        round(accuracy_score(y_true, y_pred), 4),
        "macro_f1":        round(f1_score(       y_true, y_pred, average="macro",    zero_division=0), 4),
        "weighted_f1":     round(f1_score(       y_true, y_pred, average="weighted", zero_division=0), 4),
        "macro_precision": round(precision_score(y_true, y_pred, average="macro",    zero_division=0), 4),
        "macro_recall":    round(recall_score(   y_true, y_pred, average="macro",    zero_division=0), 4),
        "per_class": {
            cls: {
                "precision": round(report[cls]["precision"], 4),
                "recall":    round(report[cls]["recall"],    4),
                "f1":        round(report[cls]["f1-score"],  4),
                "support":   int(report[cls]["support"]),
            }
            for cls in labels if cls in report
        },
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


# ── Data loading ──────────────────────────────────────────────────────────────

def load_labelled(path: str) -> pd.DataFrame:
    """Load data_annotation.xlsx and add normalised _text, _clean, _label, _label_id columns."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = pd.read_excel(path)
    df["_text"]     = df["body_training"].astype(str)
    df["_clean"]    = df["_text"].apply(normalise_text)
    df["_label"]    = df["manual_labelling"].apply(normalise_label)
    df["_label_id"] = df["_label"].map(LABEL2ID)
    return df


def load_unlabelled(path: str) -> pd.DataFrame:
    """Load singapore_wp_comments_training.csv and add _text / _clean columns."""
    df = pd.read_csv(path)
    df["_text"]  = df["body_training"].astype(str)
    df["_clean"] = df["_text"].apply(normalise_text)
    return df


def safe_val(val, cast=str):
    """Safely cast a value; return None on NaN or cast failure."""
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return cast(val)
    except (ValueError, TypeError):
        return str(val)