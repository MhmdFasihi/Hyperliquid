"""Load and validate config.json credentials."""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

CONFIG_FILENAME = "config.json"


@dataclass(frozen=True)
class Config:
    secret_key: str
    account_address: str


def load_config() -> Config:
    """Search for config.json in CWD first, then project root."""
    search_paths = [
        Path.cwd() / CONFIG_FILENAME,
        Path(__file__).resolve().parent.parent / CONFIG_FILENAME,
    ]

    config_path = None
    for p in search_paths:
        if p.exists():
            config_path = p
            break

    if config_path is None:
        print(
            f"Error: {CONFIG_FILENAME} not found. "
            "Copy config.json.example to config.json and fill in your credentials.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    with open(config_path) as f:
        raw = json.load(f)

    missing = [k for k in ("secret_key", "account_address") if k not in raw or not raw[k]]
    if missing:
        print(
            f"Error: config.json missing required fields: {', '.join(missing)}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return Config(secret_key=raw["secret_key"], account_address=raw["account_address"])
