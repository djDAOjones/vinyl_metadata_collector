# Windsurf Discogs CLI

CLI tool that enriches a vinyl record CSV by querying Discogs, following the specification in `../app_spec.md`.

## First-time setup

1. Ensure Python 3.11 is installed.
2. Create a virtual environment (recommended `python3 -m venv .venv`), then activate it.
3. Install dependencies: `pip install -e .` (run inside this directory).

## Usage

```bash
windsurf-discogs --input ../list_in.csv --output ./list_out.csv --token-file ../discogs_personal_access_token
# or, from source without installing globally:
python -m windsurf_cli.cli --input ../list_in.csv --output ./list_out.csv --token-file ../discogs_personal_access_token
```

Options:

- `--input` / `-i`: Path to the source CSV.
- `--output` / `-o`: Destination CSV to write enriched data.
- `--token`: Discogs personal access token (can use env var `DISCOGS_TOKEN`).
- `--token-file`: Path to a file containing the token (useful to keep token out of shell history).

Run `windsurf-discogs --help` for more details.
