"""Command-line entry point for the Windsurf Discogs CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .config import ConfigError, load_discogs_token
from .csv_io import (
    CSVFormatError,
    next_sequenced_path,
    read_input_csv,
    write_output_csv,
)
from .discogs_client import DiscogsClient
from .enrichment import Enricher

console = Console()


def enrich(
    input: Path = typer.Option(
        ...,
        "--input",
        "-i",
        exists=True,
        readable=True,
        help="Source spreadsheet path (.csv/.xlsx).",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Destination CSV path.",
    ),
    token: Optional[str] = typer.Option(None, "--token", help="Discogs personal access token."),
    token_file: Optional[Path] = typer.Option(
        None,
        "--token-file",
        exists=True,
        readable=True,
        help="Path to file containing the Discogs token.",
    ),
) -> None:
    """
    Enrich the input CSV and write the results to the output path.

    This chunk implements ingestion/export plus token resolution.
    Discogs API integration will follow in subsequent chunks.
    """

    try:
        discogs_token = load_discogs_token(token=token, token_file=token_file)
    except ConfigError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    console.log("Reading input file...")
    try:
        df = read_input_csv(input)
    except CSVFormatError as exc:
        console.print(f"[red]CSV error:[/red] {exc}")
        raise typer.Exit(code=3) from exc

    client = DiscogsClient(token=discogs_token)
    enricher = Enricher(client, console)

    console.log("Enriching rows via Discogs...")
    try:
        enricher.enrich_dataframe(df)
    except KeyboardInterrupt:
        console.print("[yellow]Interrupted by user. Writing partial results...[/yellow]")
        enricher.request_stop()
    finally:
        client.close()

    sequenced_output = next_sequenced_path(output)
    console.log(f"Writing output CSV to {sequenced_output}...")
    write_output_csv(df, sequenced_output)
    console.print(
        "[green]Done.[/green] Rows processed: "
        f"{len(df)}. Token length cached ({len(discogs_token)} chars). "
        f"Output: {sequenced_output.name}"
    )


def main() -> None:
    """Console-script entry point."""
    typer.run(enrich)


if __name__ == "__main__":
    main()
