"""Search planning logic for Discogs lookups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from .discogs_client import DiscogsClient
from .normalization import normalize_catalogue


@dataclass
class SearchPlan:
    row_id: Optional[str]
    provided_discogs_id: Optional[str]
    normalized_catnos: List[str]
    queries: List[Dict[str, Any]]


class SearchOrchestrator:
    """Generates Discogs search plans (queries & normalized cat numbers)."""

    def __init__(self, client: DiscogsClient) -> None:
        self.client = client

    def build_plan(self, row: Mapping[str, Any]) -> SearchPlan:
        catno_raw = str(row.get("Catalogue #", "") or "")
        label = str(row.get("Label", "") or "")
        title = str(row.get("Title", "") or "")
        discogs_id = (str(row.get("Discogs ID")) or "").strip() or None
        normalized = normalize_catalogue(catno_raw)

        search_label = _canonicalize_label(label.strip()) or _canonicalize_label(
            _infer_label_from_catno(catno_raw) or ""
        )
        title_clean = title.strip()
        artist_candidates = _candidate_artists(row)

        queries: List[Dict[str, Any]] = []
        for variant in normalized:
            queries.append({"type": "catno", "params": {"catno": variant}})

        if search_label:
            label_clean = search_label.strip()
            for variant in normalized:
                queries.append(
                    {"type": "label_catno", "params": {"label": label_clean, "catno": variant}}
                )

        if search_label and title_clean:
            queries.append(
                {
                    "type": "label_title",
                    "params": {"label": search_label.strip(), "title": title_clean},
                }
            )

        if search_label and normalized:
            queries.append(
                {"type": "q", "params": {"q": f"{search_label.strip()} {normalized[0]}"}}
            )

        # Always include title-based fallbacks (with and without label) to widen recall on tricky rows.
        if title_clean:
            queries.extend(
                _build_title_queries(
                    title=title_clean,
                    label=search_label,
                    artist_candidates=artist_candidates,
                    include_no_label=True,
                )
            )

        return SearchPlan(
            row_id=str(row.get("ID") or row.get("id") or "") or None,
            provided_discogs_id=discogs_id,
            normalized_catnos=normalized,
            queries=queries,
        )


def _build_title_queries(
    title: str,
    label: Optional[str],
    artist_candidates: List[str],
    include_no_label: bool = False,
) -> List[Dict[str, Any]]:
    """
    When catalogue numbers are unavailable, fall back to title-centric searches.

    We prefer Discogs' structured parameters (`title`, `artist`, `label`) over free-form queries
    to keep results relevant while still allowing the enrichment pipeline to proceed.
    """

    queries: List[Dict[str, Any]] = []
    params_with_label = {"title": title}
    if label:
        params_with_label["label"] = label
    queries.append({"type": "title", "params": params_with_label})

    if include_no_label:
        queries.append({"type": "title_unscoped", "params": {"title": title}})

    for artist in artist_candidates:
        queries.append({"type": "title_artist", "params": {"title": title, "artist": artist}})
    return queries


def _candidate_artists(row: Mapping[str, Any]) -> List[str]:
    """Return a list of candidate artist strings derived from Composer/Musicians/Conductor fields."""

    candidates: List[str] = []
    for field in ("Musicians", "Composer", "Conductor"):
        value = str(row.get(field) or "").strip()
        if not value:
            continue
        for part in value.split(";"):
            token = part.strip()
            if token and token not in candidates:
                candidates.append(token)
    return candidates


def _infer_label_from_catno(catno_raw: str) -> Optional[str]:
    """
    Attempt to derive a label name from the catalogue field when the dedicated label column is blank.

    We capture the leading tokens before the first numeric segment, which commonly encode the label
    (e.g., "CBS Harmony 30001" -> "CBS Harmony").
    """

    text = (catno_raw or "").strip()
    if not text:
        return None

    tokens = []
    for raw_token in text.replace("/", " ").split():
        token = raw_token.strip(" -_;:,()[]{}")
        if not token:
            continue
        if any(ch.isdigit() for ch in token):
            break
        tokens.append(token)

    if not tokens:
        return None

    inferred = " ".join(tokens).strip()
    if len(inferred) < 3:
        return None
    return inferred


def _canonicalize_label(label: str) -> Optional[str]:
    """Map common label variants to Discogs-friendly names."""

    if not label:
        return None

    canon_map = {
        "LONDON PS": "London Records",
        "LONDON": "London Records",
        "RCA RED SEAL": "RCA Red Seal",
        "CAPITOL EMI MFP": "Music For Pleasure",
        "MFP": "Music For Pleasure",
        "COLUMBIA EMI": "Columbia",
        "ANGEL": "Angel Records",
    }

    upper = label.upper()
    for key, value in canon_map.items():
        if key in upper:
            return value
    return label or None


__all__ = ["SearchOrchestrator", "SearchPlan"]
