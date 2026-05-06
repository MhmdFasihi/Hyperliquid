"""Account management commands: transfers, withdrawals, history, sub-accounts."""

import time
from typing import Any, Optional

import typer
from typing_extensions import Annotated

from hyper_cli.client import get_client
from hyper_cli.display import (
    console,
    print_ledger_history,
    print_sub_accounts,
)
from hyper_cli.responses import parse_action_response
from hyper_cli.validation import (
    canonical_decimal,
    confirm_or_exit,
    parse_usdc_amount,
    require_address,
    require_positive,
    usdc_to_micro,
)

app = typer.Typer(help="Account management commands", no_args_is_help=True)


# ── Transfers ───────────────────────────────────────────────


@app.command("spot-to-perp")
def spot_to_perp(
    amount: Annotated[str, typer.Argument(help="USDC amount to transfer to perp")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Transfer USDC from spot to perp account."""
    usdc = parse_usdc_amount("amount", amount)
    amount_str = canonical_decimal(usdc)
    confirm_or_exit(f"Transfer ${amount_str} from spot to perp?", yes)
    client = get_client()
    try:
        result = client.main_wallet_exchange.usd_class_transfer(amount_str, to_perp=True)
        _print_transfer_result(result, f"Transferred ${amount_str} spot → perp")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Transfer failed:[/red] {e}")
        raise typer.Exit(1)


@app.command("perp-to-spot")
def perp_to_spot(
    amount: Annotated[str, typer.Argument(help="USDC amount to transfer to spot")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Transfer USDC from perp to spot account."""
    usdc = parse_usdc_amount("amount", amount)
    amount_str = canonical_decimal(usdc)
    confirm_or_exit(f"Transfer ${amount_str} from perp to spot?", yes)
    client = get_client()
    try:
        result = client.main_wallet_exchange.usd_class_transfer(amount_str, to_perp=False)
        _print_transfer_result(result, f"Transferred ${amount_str} perp → spot")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Transfer failed:[/red] {e}")
        raise typer.Exit(1)


# ── Withdraw ────────────────────────────────────────────────


@app.command()
def withdraw(
    amount: Annotated[str, typer.Argument(help="USDC amount to withdraw")],
    destination: Annotated[
        Optional[str],
        typer.Option("--to", help="Destination address (defaults to your account address)"),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Withdraw USDC to an on-chain address."""
    usdc = parse_usdc_amount("amount", amount)
    amount_str = canonical_decimal(usdc)
    client = get_client()
    dest = destination or client.address
    require_address("destination", dest)
    confirm_or_exit(f"Withdraw ${amount_str} to {dest}? This requires main_wallet_secret_key.", yes)
    try:
        result = client.main_wallet_exchange.withdraw_from_bridge(amount_str, dest)
        _print_transfer_result(result, f"Withdrew ${amount_str} to {dest}")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Withdrawal failed:[/red] {e}")
        raise typer.Exit(1)


# ── History ─────────────────────────────────────────────────


@app.command()
def history(
    days: Annotated[int, typer.Option("--days", "-d", help="Look back N days")] = 7,
) -> None:
    """View non-funding transaction history (deposits, withdrawals, transfers)."""
    require_positive("days", days)
    client = get_client()
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - days * 24 * 60 * 60 * 1000
    try:
        updates = client.info.user_non_funding_ledger_updates(client.address, start_ms, end_ms)
        print_ledger_history(updates, days)
    except Exception as e:
        console.print(f"[red]Failed to fetch history:[/red] {e}")
        raise typer.Exit(1)


# ── Sub-accounts ────────────────────────────────────────────


@app.command("sub-accounts")
def sub_accounts() -> None:
    """List all sub-accounts."""
    client = get_client()
    try:
        accounts = client.info.query_sub_accounts(client.address)
        print_sub_accounts(accounts)
    except Exception as e:
        console.print(f"[red]Failed to fetch sub-accounts:[/red] {e}")
        raise typer.Exit(1)


@app.command("sub-create")
def sub_create(
    name: Annotated[str, typer.Argument(help="Name for the new sub-account")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Create a new sub-account."""
    if not name.strip():
        console.print("[red]Sub-account name cannot be empty.[/red]")
        raise typer.Exit(1)
    confirm_or_exit(f"Create sub-account '{name}'?", yes)
    client = get_client()
    try:
        result = client.main_wallet_exchange.create_sub_account(name)
        _print_transfer_result(result, f"Sub-account '{name}' created")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Failed to create sub-account:[/red] {e}")
        raise typer.Exit(1)


@app.command("sub-transfer")
def sub_transfer(
    sub_address: Annotated[str, typer.Argument(help="Sub-account address")],
    amount: Annotated[str, typer.Argument(help="USDC amount")],
    direction: Annotated[str, typer.Argument(help="deposit or withdraw")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Transfer USDC to/from a sub-account. Direction: deposit or withdraw."""
    require_address("sub_address", sub_address)
    usdc = parse_usdc_amount("amount", amount)
    amount_str = canonical_decimal(usdc)
    is_deposit = direction.lower() in ("deposit", "in")
    if direction.lower() not in ("deposit", "in", "withdraw", "out"):
        console.print("[red]Direction must be 'deposit' or 'withdraw'[/red]")
        raise typer.Exit(1)
    action = "deposit to" if is_deposit else "withdraw from"
    confirm_or_exit(f"{action.title()} sub-account {sub_address}: ${amount_str}?", yes)
    client = get_client()
    usd_int = usdc_to_micro(usdc)
    try:
        result = client.main_wallet_exchange.sub_account_transfer(sub_address, is_deposit, usd_int)
        action = "deposited to" if is_deposit else "withdrawn from"
        _print_transfer_result(result, f"${amount_str} {action} sub-account {sub_address}")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Sub-account transfer failed:[/red] {e}")
        raise typer.Exit(1)


# ── Helpers ─────────────────────────────────────────────────


def _usdc_to_micro(amount: str) -> int:
    return usdc_to_micro(parse_usdc_amount("amount", amount))


def _print_transfer_result(result: Any, success_msg: str) -> None:
    summary = parse_action_response(result)
    if summary.ok:
        console.print(f"[green]{success_msg}[/green]")
    else:
        console.print(f"[red]Failed:[/red] {result}")
        raise typer.Exit(1)
