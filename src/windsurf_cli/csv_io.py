"""CSV/XLSX ingestion and export helpers."""

from __future__ import annotations

import re
from io import StringIO
from pathlib import Path
from typing import List

import pandas as pd

from .schema import FILLABLE_COLUMNS, INPUT_COLUMNS, OUTPUT_COLUMNS


class CSVFormatError(RuntimeError):
    """Raised when the input CSV is missing required columns."""


def read_input_csv(path: Path) -> pd.DataFrame:
    """
    Load the source spreadsheet (CSV or XLSX) and ensure required headers exist.

    The loader auto-detects the format based on file suffix:
    - `.csv` (or unknown extensions) are parsed via pandas using robust encoding fallbacks.
    - `.xlsx`/`.xlsm`/`.xls` are read with :func:`pandas.read_excel`, defaulting to the first sheet.

    All fields are coerced to strings and missing values are normalized to empty strings so the
    enrichment pipeline never receives NaNs.
    """

    df = _load_dataframe(path)

    # Validate schema expectations before enrichment.
    missing = _missing_columns(df.columns.tolist(), INPUT_COLUMNS)
    if missing:
        raise CSVFormatError(
            f"Input CSV {path} is missing required columns: {', '.join(missing)}"
        )

    for column, default in FILLABLE_COLUMNS.items():
        if column not in df.columns:
            df[column] = default

    # Ensure consistent column ordering for downstream steps.
    return df.reindex(columns=_ensure_columns(df.columns.tolist(), OUTPUT_COLUMNS), fill_value="")


def write_output_csv(df: pd.DataFrame, path: Path) -> None:
    """
    Write dataframe to disk with the canonical output column order.

    Output is always UTF-8 encoded to guarantee compatibility with Excel, LibreOffice,
    and downstream scripts regardless of the host locale.
    """

    ordered = df.reindex(columns=OUTPUT_COLUMNS, fill_value="")
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered.to_csv(path, index=False, encoding="utf-8")


def _missing_columns(actual: List[str], required: List[str]) -> List[str]:
    return [col for col in required if col not in actual]


def _ensure_columns(actual: List[str], desired: List[str]) -> List[str]:
    present = [col for col in desired if col in actual]
    extras = [col for col in actual if col not in desired]
    return present + extras


def _load_dataframe(path: Path) -> pd.DataFrame:
    """
    Return a DataFrame for the given path, dispatching to CSV or Excel readers as needed.
    """

    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        df = pd.read_excel(
            path,
            dtype=str,
            keep_default_na=False,
            na_values=[],
            engine="openpyxl",
        )
    elif suffix == ".xls":
        df = pd.read_excel(
            path,
            dtype=str,
            keep_default_na=False,
            na_values=[],
        )
    else:
        buffer = _read_text_with_replacement(path)
        df = pd.read_csv(
            buffer,
            dtype=str,
            keep_default_na=False,
            na_values=[],
        )

    # pandas may still insert NaN for entirely missing columns; convert to empty strings.
    return df.fillna("")


def _read_text_with_replacement(path: Path) -> StringIO:
    """
    Return a text buffer decoded with sensible fallbacks.

    We try UTF-8 first, then common legacy encodings before falling back to
    UTF-8 with replacement. This preserves curly quotes and other cp1252
    glyphs present in the original catalog list.
    """

    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return StringIO(raw.decode(encoding))
        except UnicodeDecodeError:
            continue
    return StringIO(raw.decode("utf-8", errors="replace"))


def next_sequenced_path(path: Path, width: int = 4) -> Path:
    """
    Return the next sequential filename by appending _0001, _0002, ... before the extension.

    The numbering scans existing siblings to find the highest suffix and increments it.
    """

    directory = path.parent if str(path.parent) not in ("", ".") else Path(".")
    base = path.stem
    suffix = path.suffix
    pattern = f"{base}_*{suffix}" if suffix else f"{base}_*"
    seq_pattern = re.compile(rf"^{re.escape(base)}_(\d{{{width}}})$")

    highest = 0
    for candidate in directory.glob(pattern):
        match = seq_pattern.match(candidate.stem)
        if match:
            highest = max(highest, int(match.group(1)))

    next_value = highest + 1
    padded = f"{next_value:0{width}d}"
    new_name = f"{base}_{padded}{suffix}"
    return directory / new_name
