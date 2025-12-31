"""Catalogue number normalization utilities."""

from __future__ import annotations

import re
import unicodedata
from typing import List

NOISE_PATTERNS = [
    re.compile(r"\b(mono|stereo|stéré|lp|album|set)\b", re.IGNORECASE),
    re.compile(r"\([^)]*\)"),  # parenthetical notes
]

SEPARATOR_RUN = re.compile(r"[._\-–—]+")
WHITESPACE_RUN = re.compile(r"\s+")


def normalize_catalogue(raw: str | None) -> List[str]:
    """Return ordered unique catalogue-number variants suitable for Discogs searches."""

    if not raw:
        return []

    text = _basic_cleanup(raw)
    text = _ascii_safe(text)
    for pattern in NOISE_PATTERNS:
        text = pattern.sub(" ", text)

    text = text.strip().upper()
    if not text:
        return []

    variants: List[str] = []

    spaced = WHITESPACE_RUN.sub(" ", text)
    _add_variant(variants, spaced)

    dashy = SEPARATOR_RUN.sub("-", spaced)
    dashy = WHITESPACE_RUN.sub(" ", dashy)
    _add_variant(variants, dashy)

    nospace = re.sub(r"[^\w/]", "", spaced)
    _add_variant(variants, nospace)

    slash_split = "/".join(part.strip() for part in spaced.split("/") if part.strip())
    if slash_split and slash_split != spaced:
        _add_variant(variants, slash_split)

    digit_trim = _trim_before_first_digits(spaced)
    if digit_trim:
        _add_variant(variants, digit_trim)

    return variants


def _basic_cleanup(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("’", "'").replace("“", '"').replace("”", '"')
    normalized = normalized.replace("–", "-").replace("—", "-")
    normalized = normalized.replace("\u200b", "")
    normalized = normalized.replace("\u00a0", " ")
    normalized = normalized.replace("�", " ")
    normalized = _replace_cp1252_glitches(normalized)
    return normalized


def _add_variant(store: List[str], value: str) -> None:
    candidate = value.strip()
    if candidate and candidate not in store:
        store.append(candidate)


def _ascii_safe(value: str) -> str:
    """
    Normalize to ASCII so that stray cp1252/unicode characters (e.g., Ê, Õ) do not
    pollute catalogue numbers.
    """

    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii")


def _replace_cp1252_glitches(value: str) -> str:
    """
    Map common cp1252 glyphs that sneak into the catalog list to their ASCII equivalents.
    """

    replacements = {
        "Õ": "'",
        "Ð": "-",
        "Ò": '"',
        "Ó": '"',
        "Ê": " ",
        "Š": "S",
        "š": "s",
        "Ž": "Z",
        "ž": "z",
    }
    for bad, good in replacements.items():
        value = value.replace(bad, good)
    return value


def _trim_before_first_digits(value: str) -> str:
    """
    Drop leading tokens that lack digits (e.g., label names) so searches can match
    catalogue numbers like \"Philips 6308 177\" -> \"6308 177\".
    """

    tokens = value.split()
    for idx, token in enumerate(tokens):
        if any(ch.isdigit() for ch in token):
            trimmed = " ".join(tokens[idx:])
            return trimmed if trimmed != value else ""
    return ""


__all__ = ["normalize_catalogue"]
