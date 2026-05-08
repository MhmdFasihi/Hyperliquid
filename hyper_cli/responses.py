"""Structured parsing for Hyperliquid SDK action responses."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ActionSummary:
    ok: bool
    status: str
    filled_count: int = 0
    resting_count: int = 0
    success_count: int = 0
    error_count: int = 0
    unknown_count: int = 0
    filled_size: float = 0.0
    errors: list[str] = field(default_factory=list)
    raw: Any = None

    @property
    def has_fills(self) -> bool:
        return self.filled_count > 0 and self.filled_size > 0


def parse_action_response(response: Any) -> ActionSummary:
    if response is None:
        return ActionSummary(False, "none", errors=["No response returned."], raw=response)
    if not isinstance(response, dict):
        return ActionSummary(False, "unexpected", errors=[f"Unexpected response: {response}"], raw=response)

    status = str(response.get("status", "unknown"))
    if status != "ok":
        return ActionSummary(False, status, errors=[str(response)], raw=response)

    statuses = _extract_status_items(response)
    if not statuses:
        return ActionSummary(True, status, raw=response)

    filled_count = 0
    resting_count = 0
    success_count = 0
    error_count = 0
    unknown_count = 0
    filled_size = 0.0
    errors: list[str] = []

    for item in statuses:
        if item == "success":
            success_count += 1
            continue
        if isinstance(item, str):
            unknown_count += 1
            errors.append(f"Unknown status: {item}")
            continue
        if not isinstance(item, dict):
            unknown_count += 1
            errors.append(f"Unknown status: {item}")
            continue
        if "filled" in item:
            filled_count += 1
            filled_size += _filled_size(item["filled"])
        elif "resting" in item:
            resting_count += 1
        elif "error" in item:
            error_count += 1
            errors.append(str(item["error"]))
        else:
            unknown_count += 1
            errors.append(f"Unknown status: {item}")

    ok = error_count == 0 and unknown_count == 0
    return ActionSummary(
        ok,
        status,
        filled_count=filled_count,
        resting_count=resting_count,
        success_count=success_count,
        error_count=error_count,
        unknown_count=unknown_count,
        filled_size=filled_size,
        errors=errors,
        raw=response,
    )


def _extract_status_items(response: dict[str, Any]) -> list[Any] | None:
    data = response.get("response", {}).get("data")
    if not isinstance(data, dict):
        return None
    statuses = data.get("statuses")
    if isinstance(statuses, list):
        return statuses
    single_status = data.get("status")
    if single_status is not None:
        return [single_status]
    return None


def _filled_size(fill: Any) -> float:
    if not isinstance(fill, dict):
        return 0.0
    try:
        return float(fill.get("totalSz", 0) or 0)
    except (TypeError, ValueError):
        return 0.0
