"""Shared market-data helpers."""

import time
from typing import Any


INTERVAL_MS = {
    "1m": 60 * 1000,
    "3m": 3 * 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "2h": 2 * 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "8h": 8 * 60 * 60 * 1000,
    "12h": 12 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
    "3d": 3 * 24 * 60 * 60 * 1000,
    "1w": 7 * 24 * 60 * 60 * 1000,
    "1M": 30 * 24 * 60 * 60 * 1000,
}

MARKET_ALIASES = {
    "WTI": ("BRENTOIL",),
    "WTIOIL": ("BRENTOIL",),
}


def now_ms() -> int:
    return int(time.time() * 1000)


def normalize_dex(dex: str | None) -> str:
    return (dex or "").strip().lower()


def perp_dexs_arg(dex: str | None) -> list[str] | None:
    normalized = normalize_dex(dex)
    return [normalized] if normalized else None


def normalize_coin(info: Any, coin: str, dex: str | None = None) -> str:
    """Return the SDK-recognized market name while accepting common casing."""
    raw = coin.strip()
    normalized_dex = normalize_dex(dex)
    candidates = _market_candidates(raw, normalized_dex)
    for candidate in candidates:
        if candidate in info.name_to_coin:
            return candidate

    raw_lower = raw.lower()
    for known in info.name_to_coin:
        if known.lower() == raw_lower or (normalized_dex and known.lower() == f"{normalized_dex}:{raw_lower}"):
            return known

    return raw


def find_mid(mids: dict, aliases: dict, coin: str, dex: str | None = None) -> tuple[str, Any] | None:
    raw = coin.strip()
    normalized_dex = normalize_dex(dex)
    candidates = _market_candidates(raw, normalized_dex)

    for candidate in list(candidates):
        alias = aliases.get(candidate)
        if alias is not None:
            candidates.append(alias)

    raw_lower = raw.lower()
    for known, alias in aliases.items():
        if known.lower() == raw_lower or (normalized_dex and known.lower() == f"{normalized_dex}:{raw_lower}"):
            candidates.extend([known, alias])

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate in mids:
            return candidate, mids[candidate]

    return None


def _market_candidates(raw: str, normalized_dex: str) -> list[str]:
    base_names = [raw, raw.upper()]
    base_names.extend(MARKET_ALIASES.get(raw.upper(), ()))

    candidates: list[str] = []
    for name in base_names:
        candidates.append(name)
        if normalized_dex and ":" not in name:
            candidates.append(f"{normalized_dex}:{name}")
    return candidates


def current_funding_ctx(info: Any, coin: str) -> dict | None:
    meta, contexts = info.meta_and_asset_ctxs()
    resolved = info.name_to_coin.get(coin, coin)
    for idx, asset in enumerate(meta.get("universe", [])):
        if asset.get("name") == resolved:
            return contexts[idx]
    return None
