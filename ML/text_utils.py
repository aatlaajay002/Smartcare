"""Shared text pre-processing (kept in its own module so the saved model can be unpickled anywhere)."""
import re


def clean_text(texts):
    """Lowercase, remove punctuation, collapse whitespace."""
    return [re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(t).lower())).strip() for t in texts]
