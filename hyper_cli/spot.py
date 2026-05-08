"""Spot trading commands."""

from typing import Optional

import typer
from typing_extensions import Annotated

from hyper_cli.client import get_client
from hyper_cli.display import (
    console,
    print_balances,
    print_open_orders,
    print_and_require_success,
    print_order_status,
)
from hyper_cli.validation import confirm_or_exit, parse_side, require_positive, require_slippage

app = typer.Typer(help="Spot trading commands", no_args_is_help=True)

TIF_VALUES = {"gtc": "Gtc", "ioc": "Ioc", "alo": "Alo"}


def _resolve_tif(tif: str) -> str:
    val = TIF_VALUES.get(tif.lower())
    if val is None:
        console.print(f"[red]Invalid TIF '{tif}'. Use: gtc, ioc, alo[/red]")
        raise typer.Exit(1)
    return val


def _place_order(coin: str, is_buy: bool, sz: float, price: float, tif: str) -> None:
    require_positive("size", sz)
    require_positive("price", price)
    client = get_client()
    order_type = {"limit": {"tif": _resolve_tif(tif)}}
    try:
        result = client.exchange.order(coin, is_buy, sz, price, order_type)
        print_and_require_success(result)
    except Exception as e:
        console.print(f"[red]Order failed:[/red] {e}")
        raise typer.Exit(1)


def _market_order(coin: str, is_buy: bool, sz: float, slippage: float, yes: bool, dry_run: bool) -> None:
    require_positive("size", sz)
    require_slippage("slippage", slippage)
    side_label = "buy" if is_buy else "sell"
    console.print(f"[yellow]Preview:[/yellow] spot market {side_label} {sz} {coin} with slippage {slippage}")
    if dry_run:
        return
    confirm_or_exit(f"Place spot market {side_label} order for {sz} {coin}?", yes)
    client = get_client()
    try:
        result = client.exchange.market_open(coin, is_buy, sz, slippage=slippage)
        print_and_require_success(result)
    except Exception as e:
        console.print(f"[red]Market order failed:[/red] {e}")
        raise typer.Exit(1)


# ── Buy / Sell ──────────────────────────────────────────────


@app.command()
def buy(
    coin: Annotated[str, typer.Argument(help="Spot coin, e.g. PURR/USDC")],
    size: Annotated[float, typer.Argument(help="Order size")],
    price: Annotated[float, typer.Argument(help="Limit price")],
    tif: Annotated[str, typer.Option(help="Time in force: gtc, ioc, alo")] = "gtc",
) -> None:
    """Place a spot limit buy order."""
    _place_order(coin, is_buy=True, sz=size, price=price, tif=tif)


@app.command()
def sell(
    coin: Annotated[str, typer.Argument(help="Spot coin, e.g. PURR/USDC")],
    size: Annotated[float, typer.Argument(help="Order size")],
    price: Annotated[float, typer.Argument(help="Limit price")],
    tif: Annotated[str, typer.Option(help="Time in force: gtc, ioc, alo")] = "gtc",
) -> None:
    """Place a spot limit sell order."""
    _place_order(coin, is_buy=False, sz=size, price=price, tif=tif)


# ── Market Orders ───────────────────────────────────────────


@app.command("market-buy")
def market_buy(
    coin: Annotated[str, typer.Argument(help="Spot coin, e.g. PURR/USDC")],
    size: Annotated[float, typer.Argument(help="Order size")],
    slippage: Annotated[
        float,
        typer.Option(min=0.0, max=1.0, help="Slippage tolerance (0.05 = 5%)"),
    ] = 0.05,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print the action without signing or placing an order")] = False,
) -> None:
    """Place a spot market buy order."""
    _market_order(coin, is_buy=True, sz=size, slippage=slippage, yes=yes, dry_run=dry_run)


@app.command("market-sell")
def market_sell(
    coin: Annotated[str, typer.Argument(help="Spot coin, e.g. PURR/USDC")],
    size: Annotated[float, typer.Argument(help="Order size")],
    slippage: Annotated[
        float,
        typer.Option(min=0.0, max=1.0, help="Slippage tolerance (0.05 = 5%)"),
    ] = 0.05,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print the action without signing or placing an order")] = False,
) -> None:
    """Place a spot market sell order."""
    _market_order(coin, is_buy=False, sz=size, slippage=slippage, yes=yes, dry_run=dry_run)


# ── Cancel ──────────────────────────────────────────────────


@app.command()
def cancel(
    coin: Annotated[str, typer.Argument(help="Spot coin")],
    oid: Annotated[int, typer.Argument(help="Order ID to cancel")],
) -> None:
    """Cancel an open order by OID."""
    client = get_client()
    try:
        result = client.exchange.cancel(coin, oid)
        print_and_require_success(result)
    except Exception as e:
        console.print(f"[red]Cancel failed:[/red] {e}")
        raise typer.Exit(1)


@app.command("cancel-all")
def cancel_all(
    coin: Annotated[str, typer.Argument(help="Cancel all orders for this coin")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Cancel all open orders for a coin."""
    confirm_or_exit(f"Cancel all open spot orders for {coin}?", yes)
    client = get_client()
    try:
        open_orders = client.info.open_orders(client.address)
        matching = [o for o in open_orders if o.get("coin") == coin]
        if not matching:
            console.print(f"[yellow]No open orders for {coin}.[/yellow]")
            return
        cancel_reqs = [{"coin": coin, "oid": o["oid"]} for o in matching]
        result = client.exchange.bulk_cancel(cancel_reqs)
        print_and_require_success(result)
    except Exception as e:
        console.print(f"[red]Cancel-all failed:[/red] {e}")
        raise typer.Exit(1)


# ── Modify ──────────────────────────────────────────────────


@app.command()
def modify(
    oid: Annotated[int, typer.Argument(help="Order ID to modify")],
    coin: Annotated[str, typer.Argument(help="Spot coin")],
    side: Annotated[str, typer.Argument(help="buy or sell")],
    size: Annotated[float, typer.Argument(help="New order size")],
    price: Annotated[float, typer.Argument(help="New limit price")],
    tif: Annotated[str, typer.Option(help="Time in force: gtc, ioc, alo")] = "gtc",
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print the replacement order without signing")] = False,
) -> None:
    """Modify an existing order."""
    require_positive("size", size)
    require_positive("price", price)
    is_buy = parse_side(side, allow_position_aliases=False)
    client = get_client()
    order_type = {"limit": {"tif": _resolve_tif(tif)}}
    side_label = "buy" if is_buy else "sell"
    console.print(f"[yellow]Preview:[/yellow] modify OID {oid}: {side_label} {size} {coin} at {price}, tif={tif}")
    if dry_run:
        return
    confirm_or_exit(f"Modify spot order {oid} on {coin}?", yes)
    try:
        result = client.exchange.modify_order(oid, coin, is_buy, size, price, order_type)
        print_and_require_success(result)
    except Exception as e:
        console.print(f"[red]Modify failed:[/red] {e}")
        raise typer.Exit(1)


# ── Query Commands ──────────────────────────────────────────


@app.command()
def orders(
    coin: Annotated[Optional[str], typer.Argument(help="Filter by coin (optional)")] = None,
) -> None:
    """View open orders. Optionally filter by coin."""
    client = get_client()
    try:
        all_orders = client.info.open_orders(client.address)
        if coin:
            all_orders = [o for o in all_orders if o.get("coin") == coin]
        print_open_orders(all_orders)
    except Exception as e:
        console.print(f"[red]Failed to fetch orders:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def balances() -> None:
    """View spot balances."""
    client = get_client()
    try:
        state = client.info.spot_user_state(client.address)
        print_balances(state)
    except Exception as e:
        console.print(f"[red]Failed to fetch balances:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def status(
    oid: Annotated[int, typer.Argument(help="Order ID to check")],
) -> None:
    """Check status of a specific order by OID."""
    client = get_client()
    try:
        result = client.info.query_order_by_oid(client.address, oid)
        print_order_status(result)
    except Exception as e:
        console.print(f"[red]Failed to query order:[/red] {e}")
        raise typer.Exit(1)
