"""Transform Discogs release JSON into CSV-friendly fields."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence


def map_release_to_fields(release: Dict[str, Any]) -> Dict[str, str]:
    data: Dict[str, str] = {}

    labels = release.get("labels") or []
    if labels:
        label0 = labels[0] or {}
        data["Label"] = (label0.get("name") or "").strip()
        data["Catalogue #"] = (label0.get("catno") or "").strip()

    data["Title"] = (release.get("title") or "").strip()

    year = release.get("year")
    if not year:
        released = (release.get("released") or "").strip()
        if released:
            year = released[:4]
    if year:
        data["Year of Release"] = str(year)

    data["Track listing"] = _format_tracklist(release.get("tracklist") or [])

    stereo = _determine_stereo(release.get("formats") or [])
    if stereo:
        data["Stereo /Mono"] = stereo

    composers, conductors, musicians = _collect_people(release)
    if composers:
        data["Composer"] = "; ".join(composers)
    if conductors:
        data["Conductor"] = "; ".join(conductors)
    if musicians:
        data["Musicians"] = "; ".join(musicians)

    return data


def _format_tracklist(tracklist: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for track in tracklist:
        position = (track.get("position") or "").strip()
        title = (track.get("title") or "").strip()
        duration = (track.get("duration") or "").strip()
        if not title:
            continue
        segment_parts: List[str] = []
        if position:
            segment_parts.append(position)
        segment_parts.append(title)
        segment = " ".join(part for part in segment_parts if part)
        if duration:
            segment = f"{segment} – {duration}"
        lines.append(segment)
    return "\n".join(lines)


def _determine_stereo(formats: Iterable[Dict[str, Any]]) -> str:
    for fmt in formats:
        descriptions = [d.lower() for d in (fmt.get("descriptions") or [])]
        if any("stereo" in desc for desc in descriptions):
            return "Stereo"
        if any("mono" in desc for desc in descriptions):
            return "Mono"
    return ""


def _collect_people(release: Dict[str, Any]) -> tuple[Sequence[str], Sequence[str], Sequence[str]]:
    composers: List[str] = []
    conductors: List[str] = []
    musicians: List[str] = []

    def add_person(target: List[str], entry: Dict[str, Any], include_role: bool = False) -> None:
        name = (entry.get("name") or "").strip()
        if not name:
            return
        if include_role:
            role = (entry.get("role") or "").strip()
            if role:
                value = f"{name} ({role})"
                if value not in target:
                    target.append(value)
                return
        if name not in target:
            target.append(name)

    extra = release.get("extraartists") or []
    for entry in extra:
        role = (entry.get("role") or "").lower()
        if not role:
            continue
        if "composer" in role or "composed" in role or "written-by" in role:
            add_person(composers, entry)
        elif "conductor" in role:
            add_person(conductors, entry)
        else:
            add_person(musicians, entry, include_role=True)

    for entry in release.get("artists") or []:
        add_person(musicians, entry)

    return composers, conductors, musicians


__all__ = ["map_release_to_fields"]
