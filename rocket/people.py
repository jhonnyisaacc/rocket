"""Explicit person aliases; no fuzzy identity joins."""

import re

ALIASES = {
    "nancy_pelosi": {"nancy pelosi", "pelosi nancy", "nancy patricia pelosi"},
    "donald_trump": {"donald trump", "donald j trump", "donald john trump", "trump donald j", "trump donald"},
}


def person_id(name):
    normalized = re.sub(r"\b(?:hon|honorable)\b", " ", str(name).lower())
    normalized = " ".join(re.sub(r"[^a-z ]", " ", normalized).split())
    return next((key for key, aliases in ALIASES.items() if normalized in aliases), None)
