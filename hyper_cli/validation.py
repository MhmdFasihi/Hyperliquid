"""Validation and confirmation helpers for command handlers."""

from decimal import Decimal, InvalidOperation
import math
import re
from typing import Any

from eth_account import Account
import typer

from hyper_cli.display import console

BUY_ALIASES = {"buy", "b", "long"}
SELL_ALIASES = {"sell", "s", "short"}
USDC_RE = re.compile(r"^(0|[1-9][0-9]*)(\.[0-9]{1,6})?$")


def parse_side(side: str, *, allow_position_aliases: bool = True) -> bool:
    """Return True for buy/long and False for sell/short, rejecting unknown values."""
    value = side.lower().strip()
    buy_values = BUY_ALIASES if allow_position_aliases else {"buy", "b"}
    sell_values = SELL_ALIASES if allow_position_aliases else {"sell", "s"}

    if value in buy_values:
        return True
    if value in sell_values:
        return False

    allowed = sorted(buy_values | sell_values)
    console.print(f"[red]Invalid side '{side}'. Use one of: {', '.join(allowed)}[/red]")
    raise typer.Exit(1)


def require_positive(name: str, value: float | int) -> None:
    require_finite(name, value)
    if value <= 0:
        console.print(f"[red]{name} must be greater than 0.[/red]")
        raise typer.Exit(1)


def require_non_negative(name: str, value: float | int) -> None:
    require_finite(name, value)
    if value < 0:
        console.print(f"[red]{name} must be 0 or greater.[/red]")
        raise typer.Exit(1)


def require_at_most(name: str, value: float | int, max_value: float | int) -> None:
    require_finite(name, value)
    if value > max_value:
        console.print(f"[red]{name} must be at most {max_value}.[/red]")
        raise typer.Exit(1)


def require_finite(name: str, value: float | int) -> None:
    if not isinstance(value, int) and not math.isfinite(float(value)):
        console.print(f"[red]{name} must be a finite number.[/red]")
        raise typer.Exit(1)


def require_slippage(name: str, value: float) -> None:
    """Validate slippage expressed as a decimal fraction, e.g. 0.01 for 1%."""
    require_non_negative(name, value)
    require_at_most(name, value, 1.0)


def is_valid_private_key(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("0x") or len(value) != 66:
        return False
    try:
        int(value[2:], 16)
    except ValueError:
        return False
    return True


def is_valid_address(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("0x") or len(value) != 42:
        return False
    try:
        int(value[2:], 16)
    except ValueError:
        return False
    return True


def require_address(name: str, value: str) -> None:
    if not is_valid_address(value):
        console.print(f"[red]{name} must be a 0x-prefixed 20-byte address.[/red]")
        raise typer.Exit(1)


def derive_address(private_key: str) -> str:
    return Account.from_key(private_key).address


def parse_usdc_amount(name: str, raw: str) -> Decimal:
    """Parse a user-entered USDC amount without losing decimal precision."""
    value = raw.strip()
    if "e" in value.lower() or not USDC_RE.match(value):
        console.print(f"[red]{name} must be a decimal USDC amount with at most 6 decimal places.[/red]")
        raise typer.Exit(1)
    try:
        amount = Decimal(value)
    except InvalidOperation:
        console.print(f"[red]{name} must be a valid decimal USDC amount.[/red]")
        raise typer.Exit(1)
    if not amount.is_finite() or amount <= 0:
        console.print(f"[red]{name} must be greater than 0.[/red]")
        raise typer.Exit(1)
    return amount


def canonical_decimal(amount: Decimal) -> str:
    normalized = amount.normalize()
    if normalized == normalized.to_integral_value():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f")


def usdc_to_micro(amount: Decimal) -> int:
    scaled = amount * Decimal("1000000")
    if scaled != scaled.to_integral_value():
        console.print("[red]amount supports at most 6 decimal places.[/red]")
        raise typer.Exit(1)
    return int(scaled)


def confirm_or_exit(message: str, yes: bool) -> None:
    """Require explicit confirmation for destructive or fund-moving commands."""
    if yes:
        return
    if not typer.confirm(message):
        console.print("[yellow]Aborted.[/yellow]")
        raise typer.Exit(1)
