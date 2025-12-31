"""Column definitions shared across the CLI."""

from __future__ import annotations

INPUT_COLUMNS = [
    "ID",
    "Composer",
    "Conductor",
    "Musicians",
    "Title",
    "Label",
    "Catalogue #",
    "Year of Recording (if known)",
    "Year of Release",
    "Stereo /Mono",
    "Track listing",
    "Discogs ID",
    "Discogs URL",
    "Discogs ID confidence",
    "Discogs ID Score",
]

OUTPUT_COLUMNS = [
    "ID",
    "Composer",
    "Conductor",
    "Musicians",
    "Title",
    "Label",
    "Catalogue #",
    "Year of Recording (if known)",
    "Year of Release",
    "Stereo /Mono",
    "Track listing",
    "Discogs ID",
    "Discogs URL",
    "Discogs record found?",
    "Discogs ID confidence",
    "Discogs ID Score",
]

# Columns that might be missing in the input but are required in the output.
FILLABLE_COLUMNS = {
    "Label": "",
    "Discogs URL": "",
    "Discogs record found?": "No",
    "Discogs ID Score": "",
}
