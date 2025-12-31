"""Column definitions shared across the CLI."""

from __future__ import annotations

INPUT_COLUMNS = [
    "ID",
    "Composer",
    "Conductor",
    "Musicians",
    "Title",
    "Catalogue #",
    "Year of Recording (if known)",
    "Year of Release",
    "Stereo /Mono",
    "Track listing",
    "Discogs ID",
    "Discogs ID confidence",
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
    "Discogs record found?",
    "Discogs ID confidence",
]

# Columns that might be missing in the input but are required in the output.
FILLABLE_COLUMNS = {
    "Label": "",
    "Discogs record found?": "No",
}
