"""
Infers the regional language of a Mann Ki Baat video from its title/description.

Each edition's "Regional Languages" playlist contains one video per language,
distinguished only by a suffix/prefix on the title (e.g. "... - Tamil",
"(Bengali)", "Mann Ki Baat | Telugu"). Title conventions aren't perfectly
consistent across 136 editions, so this is alias-based and returns None
(rather than a guess) when nothing matches, so unmatched rows can be
reviewed manually instead of silently mislabeled.
"""
import re
from typing import Optional

# Canonical language name -> aliases/spellings seen in the wild.
LANGUAGE_ALIASES = {
    "Hindi": ["hindi"],
    "English": ["english"],
    "Assamese": ["assamese", "asomiya"],
    "Bengali": ["bengali", "bangla"],
    "Bodo": ["bodo"],
    "Dogri": ["dogri"],
    "Gujarati": ["gujarati"],
    "Kannada": ["kannada"],
    "Kashmiri": ["kashmiri"],
    "Konkani": ["konkani"],
    "Maithili": ["maithili"],
    "Malayalam": ["malayalam"],
    "Manipuri": ["manipuri", "meitei"],
    "Marathi": ["marathi"],
    "Nepali": ["nepali"],
    "Odia": ["odia", "oriya"],
    "Punjabi": ["punjabi"],
    "Sanskrit": ["sanskrit"],
    "Santali": ["santali"],
    "Sindhi": ["sindhi"],
    "Tamil": ["tamil"],
    "Telugu": ["telugu"],
    "Urdu": ["urdu"],
}

_ALIAS_TO_CANONICAL = {
    alias.lower(): canonical
    for canonical, aliases in LANGUAGE_ALIASES.items()
    for alias in aliases
}

# Longest alias first so shorter substrings never shadow a longer match.
_ALIAS_PATTERN = re.compile(
    r"(?<![a-z])(" + "|".join(sorted(_ALIAS_TO_CANONICAL, key=len, reverse=True)) + r")(?![a-z])",
    re.IGNORECASE,
)


def detect_language(title: str, description: str = "") -> Optional[str]:
    """Return the canonical language name, or None if no alias matched."""
    for text in (title, description):
        if not text:
            continue
        match = _ALIAS_PATTERN.search(text)
        if match:
            return _ALIAS_TO_CANONICAL[match.group(1).lower()]
    return None
