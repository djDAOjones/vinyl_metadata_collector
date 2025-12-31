"""End-to-end enrichment logic using Discogs client and search plans."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import typer

from .discogs_client import DiscogsClient, DiscogsError
from .release_mapping import map_release_to_fields
from .search_orchestrator import SearchOrchestrator, SearchPlan


@dataclass
class RowEnrichment:
    found: bool
    discogs_id: Optional[int]
    confidence: str
    fields: Dict[str, str]
    message: str = ""


class Enricher:
    def __init__(
        self,
        client: DiscogsClient,
        console: typer.rich_utils.Console,
        row_delay: float = 0.5,
        debug_scoring: bool = False,
    ) -> None:
        self.client = client
        self.console = console
        self.orchestrator = SearchOrchestrator(client)
        self.row_delay = row_delay
        self._release_cache: Dict[int, Dict[str, Any]] = {}
        self._search_cache: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], Dict[str, Any]] = {}
        self._stop_requested = False
        self._debug_scoring = debug_scoring

    def _get_release_cached(self, release_id: int) -> Dict[str, Any]:
        """Fetch a release once per run and reuse subsequent requests."""
        if release_id not in self._release_cache:
            release = self.client.get_release(release_id)
            self._release_cache[release_id] = release
        return self._release_cache[release_id]

    def request_stop(self) -> None:
        """Signal that enrichment should stop after the current row finishes."""
        self._stop_requested = True

    def enrich_dataframe(self, df) -> List[RowEnrichment]:  # type: ignore[override]
        """Iterate over the dataframe, logging progress for each row."""

        results: List[RowEnrichment] = []
        total_rows = len(df)
        for position, (idx, row) in enumerate(df.iterrows(), start=1):
            if self._stop_requested:
                self._log("[yellow]Stop requested; finishing run early.[/yellow]")
                break
            self._log_row_start(row, position, total_rows)
            plan = self.orchestrator.build_plan(row)
            self._log_plan_summary(plan)
            try:
                enrichment = self._enrich_row(row, plan)
            except DiscogsError as exc:
                self.console.print(
                    f"[red]Discogs error row {idx}:[/red] {exc.message} "
                    f"(status {exc.status_code})"
                )
                enrichment = RowEnrichment(
                    found=False,
                    discogs_id=None,
                    confidence="Error",
                    fields={},
                    message=exc.message,
                )

            self._apply_enrichment(df, idx, enrichment)
            results.append(enrichment)
            time.sleep(self.row_delay)
            if self._stop_requested:
                self._log("[yellow]Stop requested; finishing run early after row.[/yellow]")
                break
        return results

    def _apply_enrichment(self, df, idx: int, enrichment: RowEnrichment) -> None:
        for field, value in enrichment.fields.items():
            if value:
                df.at[idx, field] = value
        df.at[idx, "Discogs ID"] = enrichment.discogs_id or df.at[idx, "Discogs ID"]
        df.at[idx, "Discogs record found?"] = "Yes" if enrichment.found else "No"
        df.at[idx, "Discogs ID confidence"] = enrichment.confidence

    def _enrich_row(self, row: Mapping[str, Any], plan: SearchPlan) -> RowEnrichment:
        label = str(row.get("Label") or "").strip()
        title = str(row.get("Title") or "").strip()

        if plan.provided_discogs_id:
            try:
                release_id = int(plan.provided_discogs_id)
            except ValueError:
                release_id = None
            if release_id:
                self._log(f"    ↳ Fetching provided Discogs ID {release_id}")
                try:
                    release = self._get_release_cached(release_id)
                    fields = map_release_to_fields(release)
                    return RowEnrichment(
                        found=True,
                        discogs_id=release_id,
                        confidence=plan.provided_confidence or "Manual",
                        fields=fields,
                    )
                except DiscogsError as exc:
                    if exc.status_code != 404:
                        raise
                    self.console.print(
                        f"[yellow]Discogs ID {release_id} not found; falling back to search.[/yellow]"
                    )

        expected_year = _parse_year(row.get("Year of Release") or row.get("Year"))
        candidate = self._search_for_candidate(plan, label, title, expected_year)
        if not candidate:
            self._log("    ↳ No matching Discogs release found.")
            return RowEnrichment(
                found=False,
                discogs_id=None,
                confidence="Not found",
                fields={},
            )

        release = self._get_release_cached(candidate["release_id"])
        fields = map_release_to_fields(release)
        self._log(
            f"    ↳ Selected release {candidate['release_id']} ({candidate['confidence']})"
        )
        return RowEnrichment(
            found=True,
            discogs_id=release.get("id"),
            confidence=candidate["confidence"],
            fields=fields,
        )

    def _search_for_candidate(
        self,
        plan: SearchPlan,
        label: str,
        title: str,
        expected_year: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        best: Optional[Dict[str, Any]] = None
        normalized_simple = [_simple_norm(v) for v in plan.normalized_catnos]

        for query in plan.queries:
            params = {"type": "release", "per_page": 5}
            params.update(query["params"])
            cache_key = (query["type"], tuple(sorted(params.items())))
            self._log(f"    ↳ Searching [{query['type']}] {self._summarize_params(params)}")
            if cache_key in self._search_cache:
                response = self._search_cache[cache_key]
            else:
                response = self.client.search(**params)
                self._search_cache[cache_key] = response
            for result in response.get("results", []):
                if (result.get("type") or "").lower() != "release":
                    continue
                release_id = result.get("id")
                if not release_id:
                    continue
                score, confidence = self._score_result(
                    result, normalized_simple, label, title, expected_year
                )
                if score <= 0:
                    continue
                candidate = {
                    "score": score,
                    "confidence": confidence,
                    "release_id": int(release_id),
                }
                if not best or candidate["score"] > best["score"]:
                    best = candidate

            if best and best["confidence"] == "Exact":
                break

        return best

    def _log_row_start(self, row: Mapping[str, Any], position: int, total: int) -> None:
        label = str(row.get("ID") or row.get("id") or position)
        title = (row.get("Title") or "").strip() or "<Untitled>"
        self._log(f"[cyan]Row {position}/{total}[/cyan] ID {label}: {title}")

    def _log_plan_summary(self, plan: SearchPlan) -> None:
        if plan.provided_discogs_id:
            self._log(f"    ↳ Provided Discogs ID: {plan.provided_discogs_id}")
        if plan.normalized_catnos:
            variants = ", ".join(plan.normalized_catnos[:3])
            more = "…" if len(plan.normalized_catnos) > 3 else ""
            self._log(f"    ↳ Catalogue variants: {variants}{more}")

    def _summarize_params(self, params: Mapping[str, Any]) -> str:
        interesting = []
        for key in ("catno", "label", "title", "q"):
            if key in params and params[key]:
                interesting.append(f"{key}={params[key]}")
        return ", ".join(interesting) or "no filters"

    def _log(self, message: str) -> None:
        self.console.log(message)

    def _score_result(
        self,
        result: Mapping[str, Any],
        normalized_catnos: Sequence[str],
        label: str,
        title: str,
        expected_year: Optional[int],
    ) -> tuple[int, str]:
        score = 0
        confidence = "Fallback"
        catno = _simple_norm(result.get("catno"))
        overlap_hits = 0
        exact_cat = False

        # Catalogue matching
        if catno and normalized_catnos:
            if catno in normalized_catnos:
                score += 120
                confidence = "Exact"
                exact_cat = True
            else:
                # Partial token overlaps; boost multi-token hits.
                overlap_hits = sum(
                    1 for variant in normalized_catnos if variant and (catno in variant or variant in catno)
                )
                if overlap_hits >= 2:
                    score += 90 + overlap_hits * 12
                    confidence = "Label+Cat"
                elif overlap_hits == 1:
                    score += 50
                    confidence = "Label+Cat"

        # Label alignment
        labels = result.get("label") or []
        labels_lower = [(candidate or "").lower() for candidate in labels]
        label_match = False
        if label:
            label_lower = label.lower()
            for candidate in labels:
                if label_lower in (candidate or "").lower():
                    score += 30
                    label_match = True
                    if confidence == "Fallback":
                        confidence = "Label+Cat"
                    break

        # Title alignment (lightweight)
        title_match = False
        if title:
            result_title = (result.get("title") or "").lower()
            if title.lower() in result_title:
                score += 10
                title_match = True
                if confidence == "Fallback":
                    confidence = "Title"

        # Guardrails:
        # - Avoid title-only matches when we have cat/label signals and no label intersection.
        if title_match and not catno and (label and not label_match):
            score = 0
            confidence = "Fallback"

        # If label provided and no label match and no cat overlap, drop.
        if label and not label_match and score and not exact_cat and overlap_hits == 0:
            score = 0
            confidence = "Fallback"

        # Soft year bias
        release_year = result.get("year")
        year_diff = None
        if expected_year and isinstance(release_year, int):
            year_diff = abs(release_year - expected_year)
            if year_diff <= 1:
                score += 12
            elif year_diff <= 3:
                score += 6

        # Require some minimum alignment when catnos provided
        if normalized_catnos and score < 20:
            score = 0
            confidence = "Fallback"

        if self._debug_scoring:
            self._log(
                f"      score={score} conf={confidence} catno={catno} overlap={overlap_hits} "
                f"label_match={label_match} labels={labels_lower} title_match={title_match} year_diff={year_diff}"
            )

        return score, confidence


def _simple_norm(value: Optional[str]) -> str:
    if not value:
        return ""
    return "".join(ch for ch in value.upper() if ch.isalnum())


def _parse_year(value: Any) -> Optional[int]:
    """Best-effort year parsing."""

    if value is None:
        return None
    try:
        year = int(str(value).strip())
    except (ValueError, TypeError):
        return None
    return year if 0 < year < 3000 else None


__all__ = ["Enricher", "RowEnrichment"]
