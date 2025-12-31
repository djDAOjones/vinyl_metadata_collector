"""Configuration helpers for the Windsurf Discogs CLI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


class ConfigError(RuntimeError):
    """Raised when configuration loading fails."""


def load_discogs_token(
    *,
    token: Optional[str] = None,
    token_file: Optional[Path] = None,
    env_var: str = "DISCOGS_TOKEN",
) -> str:
    """
    Resolve the Discogs token from CLI options or environment variables.

    Preference order:
        1. Explicit --token value.
        2. Contents of --token-file.
        3. Environment variable (defaults to DISCOGS_TOKEN).
    """

    if token:
        return token.strip()

    if token_file:
        try:
            file_token = token_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise ConfigError(f"Token file not found: {token_file}") from exc
        if not file_token:
            raise ConfigError(f"Token file {token_file} is empty.")
        return file_token

    env_token = os.getenv(env_var, "").strip()
    if env_token:
        return env_token

    raise ConfigError(
        "Discogs token not provided. Pass --token, --token-file, "
        f"or set the {env_var} environment variable."
    )
