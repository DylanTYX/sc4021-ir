"""
Reusable preprocessing pipeline for Singapore political Reddit text.

Pipeline order:
1. Microtext normalization
    - Remove URLs/@mentions and lowercase text.
2. Alias and entity canonicalization (rule-based)
    - Expand slang (e.g., sgp -> singapore) and map party/person aliases to entity tokens.
3. Phrase chunk normalization
    - Collapse configured multi-word phrases into single underscore tokens.
4. Tokenization
    - Split text into words, entity tokens, numbers, and punctuation.
5. Filler/noise removal
    - Drop configured filler particles (e.g., lah, lor, leh).
6. Case normalization at token level
    - Lowercase non-entity tokens.
7. Context extraction via negation scope
    - Convert negation cues to "not" and carry short-scope negation context.
8. Entity restoration
    - Convert internal entity tokens back to readable canonical names.
9. Surface-form cleanup
    - Detokenize and normalize spacing around punctuation.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# Words to silently drop (Singlish particles, internet noise)
FILLER_WORDS = {
    "lah",
    "lor",
    "leh",
    "meh",
    "sia",
    "ah",
    "hor",
    "loh",
    "lol",
    "lmao",
    "rofl",
    "omg",
}

# Short-form slang -> expanded English
SLANG_MAP = {
    "govt": "government",
    "sg": "singapore",
    "sgp": "singapore",
    "u": "you",
    "ur": "your",
    "pls": "please",
    "wif": "with",
    "abt": "about",
    "bcos": "because",
    "cos": "because",
    "coz": "because",
    "idk": "i do not know",
    "imo": "in my opinion",
    "imho": "in my humble opinion",
    "tbh": "to be honest",
    "ngl": "not going to lie",
    "ikr": "i know right",
    "btw": "by the way",
    "asap": "as soon as possible",
    "wfh": "work from home",
    "cpf": "central provident fund",
    "kpkb": "complain",
    "bo bian": "no choice",
}

# Political party aliases -> canonical name
PARTY_MAP = {
    "wp": "Workers Party",
    "workers party": "Workers Party",
    "worker party": "Workers Party",
    "workers' party": "Workers Party",
    "pap": "Peoples Action Party",
    "people action party": "Peoples Action Party",
    "people's action party": "Peoples Action Party",
    "psp": "Progress Singapore Party",
    "progress singapore party": "Progress Singapore Party",
    "sdp": "Singapore Democratic Party",
    "singapore democratic party": "Singapore Democratic Party",
    "rp": "Reform Party",
    "reform party": "Reform Party",
    "rdu": "Red Dot United",
    "red dot united": "Red Dot United",
}

# Politician aliases -> canonical name
PERSON_MAP = {
    "pritam": "Pritam Singh",
    "ps": "Pritam Singh",
    "pritam singh": "Pritam Singh",
    "sylvia": "Sylvia Lim",
    "sylvia lim": "Sylvia Lim",
    "jamus": "Jamus Lim",
    "jamus lim": "Jamus Lim",
    "he ting ru": "He Ting Ru",
    "ting ru": "He Ting Ru",
    "gerald": "Gerald Giam",
    "gerald giam": "Gerald Giam",
    "lee hsien loong": "Lee Hsien Loong",
    "lhl": "Lee Hsien Loong",
    "pm lee": "Lee Hsien Loong",
    "lee kuan yew": "Lee Kuan Yew",
    "lky": "Lee Kuan Yew",
    "lawrence wong": "Lawrence Wong",
    "lw": "Lawrence Wong",
    "pm wong": "Lawrence Wong",
    "vivian": "Vivian Balakrishnan",
    "vivian balakrishnan": "Vivian Balakrishnan",
    "chan chun sing": "Chan Chun Sing",
    "ccs": "Chan Chun Sing",
    "ong ye kung": "Ong Ye Kung",
    "oyk": "Ong Ye Kung",
}

# Multi-word topic phrases to collapse into a single token
PHRASE_TERMS = [
    "foreign policy",
    "cost of living",
    "public housing",
    "housing policy",
    "living cost",
    "minimum wage",
    "carbon tax",
    "public transport",
    "health care",
    "social welfare",
]

# Negation cues that trigger scope marking
NEGATION_CUES = {
    "no",
    "not",
    "never",
    "cannot",
    "cant",
    "can't",
    "dont",
    "don't",
    "didnt",
    "didn't",
    "isnt",
    "isn't",
    "wasnt",
    "wasn't",
    "wont",
    "won't",
    "shouldnt",
    "shouldn't",
    "couldnt",
    "couldn't",
    "wouldnt",
    "wouldn't",
    "aint",
    "ain't",
}

# How many content words after a negation cue to keep in scope
NEGATION_SCOPE = 2

# Punctuation that breaks negation scope
SCOPE_BREAKERS = {".", "!", "?", ";", ":"}

# Function-class words that do not consume the negation window
NEGATION_SKIP_WORDS = {
    "a",
    "an",
    "the",
    "to",
    "for",
    "of",
    "in",
    "on",
    "at",
    "by",
    "with",
    "and",
    "or",
    "but",
    "if",
    "that",
    "this",
    "i",
    "you",
    "he",
    "she",
    "we",
    "they",
    "it",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
}

URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
MENTION_RE = re.compile(r"(?<![a-z0-9])@[a-z0-9._-]+", flags=re.IGNORECASE)


def _canonical_to_token(name: str) -> str:
    slug = re.sub(r"[^a-z0-9\s]", "", name.lower())
    slug = re.sub(r"\s+", "_", slug).strip("_")
    return f"ent_{slug}"


def _token_to_text(token: str) -> str:
    return token.removeprefix("ent_").replace("_", " ")


ALIAS_MAP: dict[str, str] = {
    **{k.lower(): v for k, v in SLANG_MAP.items()},
    **{k.lower(): _canonical_to_token(v) for k, v in PARTY_MAP.items()},
    **{k.lower(): _canonical_to_token(v) for k, v in PERSON_MAP.items()},
}
_aliases_sorted = sorted(ALIAS_MAP, key=len, reverse=True)
ALIAS_RE = re.compile(
    r"(?<![a-z0-9])(?:"
    + "|".join(re.escape(a) for a in _aliases_sorted)
    + r")(?![a-z0-9])",
    flags=re.IGNORECASE,
)

PHRASE_PATTERNS = [
    (
        re.compile(
            r"(?<![a-z0-9])" + re.escape(p).replace(r"\ ", r"\s+") + r"(?![a-z0-9])",
            flags=re.IGNORECASE,
        ),
        p.strip().lower().replace(" ", "_"),
    )
    for p in sorted(PHRASE_TERMS, key=len, reverse=True)
]

TOKEN_RE = re.compile(
    r"ent_[a-z0-9_]+|[a-z]+(?:['-][a-z]+)*|\d+(?:\.\d+)?|[^\w\s]",
    flags=re.IGNORECASE,
)
WORD_RE = re.compile(r"^[a-z][a-z0-9_'-]*$", flags=re.IGNORECASE)


def step_clean_noise(text: str) -> str:
    text = URL_RE.sub(" ", text)
    text = MENTION_RE.sub(" ", text)
    return text.lower()


def step_normalize_aliases(text: str) -> str:
    return ALIAS_RE.sub(lambda m: ALIAS_MAP[m.group(0).lower()], text)


def step_normalize_phrases(text: str) -> str:
    for pattern, replacement in PHRASE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def step_tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text)


def step_remove_fillers(tokens: list[str]) -> list[str]:
    return [
        tok
        for tok in tokens
        if tok.startswith("ent_")
        or not (WORD_RE.match(tok) and tok.lower() in FILLER_WORDS)
    ]


def step_lowercase(tokens: list[str]) -> list[str]:
    return [tok if tok.startswith("ent_") else tok.lower() for tok in tokens]


def step_handle_negation(tokens: list[str], scope: int = NEGATION_SCOPE) -> list[str]:
    result: list[str] = []
    remaining = 0

    for tok in tokens:
        low = tok.lower()

        if tok in SCOPE_BREAKERS:
            remaining = 0
            result.append(tok)
            continue

        if low in NEGATION_CUES:
            result.append("not")
            remaining = scope
            continue

        if tok.startswith("ent_"):
            result.append(tok)
            continue

        result.append(low)

        if remaining > 0 and WORD_RE.match(tok) and low not in NEGATION_SKIP_WORDS:
            remaining -= 1

    return result


def step_restore_entities(tokens: list[str]) -> list[str]:
    return [_token_to_text(tok) if tok.startswith("ent_") else tok for tok in tokens]


def _detokenize(tokens: list[str]) -> str:
    s = " ".join(tokens)
    s = re.sub(r"\s+([.,!?;:%])", r"\1", s)
    s = re.sub(r"\s+['']s\b", "'s", s)
    return re.sub(r"\s+", " ", s).strip()


def preprocess_text(text: object) -> str:
    if pd.isna(text):
        return ""

    s = str(text)
    s = step_clean_noise(s)
    s = step_normalize_aliases(s)
    s = step_normalize_phrases(s)

    tokens = step_tokenize(s)
    tokens = step_remove_fillers(tokens)
    tokens = step_lowercase(tokens)
    tokens = step_handle_negation(tokens)
    tokens = step_restore_entities(tokens)

    return _detokenize(tokens)


def preprocess_excel_file(
    input_path: str | Path,
    text_col: str,
    output_path: str | Path,
) -> pd.DataFrame:
    """Load, preprocess, and save an Excel file with clean_text output."""
    input_path = Path(input_path)
    output_path = Path(output_path)

    df = pd.read_excel(input_path)
    if text_col not in df.columns:
        raise ValueError(f"Missing required column: {text_col}")

    df[text_col] = df[text_col].astype("string")
    df["clean_text"] = df[text_col].map(preprocess_text)
    df.to_excel(output_path, index=False)
    return df
