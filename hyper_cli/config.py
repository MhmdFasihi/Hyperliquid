"""Load and validate config.json credentials."""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from hyperliquid.utils import constants

from hyper_cli.validation import derive_address, is_valid_address, is_valid_private_key

CONFIG_FILENAME = "config.json"
NETWORKS = {
    "mainnet": constants.MAINNET_API_URL,
    "testnet": constants.TESTNET_API_URL,
}


@dataclass(frozen=True)
class Config:
    secret_key: str
    account_address: str
    main_wallet_secret_key: Optional[str] = None
    network: str = "mainnet"
    api_url: str = constants.MAINNET_API_URL


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

    try:
        with open(config_path) as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"Error: {config_path} is not valid JSON: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if not isinstance(raw, dict):
        print(f"Error: {config_path} must contain a JSON object.", file=sys.stderr)
        raise SystemExit(1)

    secret_key = raw.get("agent_secret_key") or raw.get("secret_key")
    account_address = raw.get("account_address")
    main_wallet_secret_key = raw.get("main_wallet_secret_key")
    network = _normalize_network(raw.get("network") or os.environ.get("HYPERLIQUID_NETWORK") or "mainnet")

    missing = []
    if not secret_key:
        missing.append("agent_secret_key")
    if not account_address:
        missing.append("account_address")
    if missing:
        print(
            f"Error: config.json missing required fields: {', '.join(missing)}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    _validate_private_key(secret_key, "agent_secret_key")
    _validate_address(account_address, "account_address")
    if derive_address(secret_key).lower() == account_address.lower():
        print(
            "Error: agent_secret_key resolves to account_address. "
            "Use an API agent key for trading, not the main wallet private key.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if main_wallet_secret_key:
        _validate_private_key(main_wallet_secret_key, "main_wallet_secret_key")

    return Config(
        secret_key=secret_key,
        account_address=account_address,
        main_wallet_secret_key=main_wallet_secret_key,
        network=network,
        api_url=NETWORKS[network],
    )


def public_api_url() -> str:
    """Resolve the API URL for unauthenticated public commands."""
    network = _normalize_network(os.environ.get("HYPERLIQUID_NETWORK") or "mainnet")
    return NETWORKS[network]


def _validate_private_key(value: str, name: str) -> None:
    if not is_valid_private_key(value):
        print(f"Error: config.json field {name} must be a 0x-prefixed 32-byte private key.", file=sys.stderr)
        raise SystemExit(1)


def _validate_address(value: str, name: str) -> None:
    if not is_valid_address(value):
        print(f"Error: config.json field {name} must be a 0x-prefixed 20-byte address.", file=sys.stderr)
        raise SystemExit(1)


def _normalize_network(value: str) -> str:
    network = str(value).strip().lower()
    if network not in NETWORKS:
        allowed = ", ".join(sorted(NETWORKS))
        print(f"Error: network must be one of: {allowed}.", file=sys.stderr)
        raise SystemExit(1)
    return network
