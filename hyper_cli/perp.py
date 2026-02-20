"""Perpetual trading commands."""

from typing import Optional

import typer
from typing_extensions import Annotated

from hyper_cli.client import get_client
from hyper_cli.display import (
    console,
    print_open_orders,
    print_order_response,
    print_order_status,
    print_positions,
    print_account_summary,
)

app = typer.Typer(help="Perpetual trading commands", no_args_is_help=True)

TIF_VALUES = {"gtc": "Gtc", "ioc": "Ioc", "alo": "Alo"}


def _resolve_tif(tif: str) -> str:
    val = TIF_VALUES.get(tif.lower())
    if val is None:
        console.print(f"[red]Invalid TIF '{tif}'. Use: gtc, ioc, alo[/red]")
        raise typer.Exit(1)
    return val


# ── Long / Short (Limit) ───────────────────────────────────


@app.command()
def long(
    coin: Annotated[str, typer.Argument(help="Perp coin, e.g. ETH, BTC")],
    size: Annotated[float, typer.Argument(help="Order size")],
    price: Annotated[float, typer.Argument(help="Limit price")],
    tif: Annotated[str, typer.Option(help="Time in force: gtc, ioc, alo")] = "gtc",
) -> None:
    """Place a limit long (buy) order."""
    client = get_client()
    order_type = {"limit": {"tif": _resolve_tif(tif)}}
    try:
        result = client.exchange.order(coin, True, size, price, order_type)
        print_order_response(result)
    except Exception as e:
        console.print(f"[red]Long order failed:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def short(
    coin: Annotated[str, typer.Argument(help="Perp coin, e.g. ETH, BTC")],
    size: Annotated[float, typer.Argument(help="Order size")],
    price: Annotated[float, typer.Argument(help="Limit price")],
    tif: Annotated[str, typer.Option(help="Time in force: gtc, ioc, alo")] = "gtc",
) -> None:
    """Place a limit short (sell) order."""
    client = get_client()
    order_type = {"limit": {"tif": _resolve_tif(tif)}}
    try:
        result = client.exchange.order(coin, False, size, price, order_type)
        print_order_response(result)
    except Exception as e:
        console.print(f"[red]Short order failed:[/red] {e}")
        raise typer.Exit(1)


# ── Market Orders ───────────────────────────────────────────


@app.command("market-open")
def market_open(
    coin: Annotated[str, typer.Argument(help="Perp coin, e.g. ETH")],
    side: Annotated[str, typer.Argument(help="buy or sell")],
    size: Annotated[float, typer.Argument(help="Order size")],
    slippage: Annotated[float, typer.Option(help="Slippage tolerance (0.01 = 1%%)")] = 0.01,
) -> None:
    """Market open a perp position."""
    is_buy = side.lower() in ("buy", "b", "long")
    client = get_client()
    try:
        result = client.exchange.market_open(coin, is_buy, size, None, slippage)
        print_order_response(result)
    except Exception as e:
        console.print(f"[red]Market open failed:[/red] {e}")
        raise typer.Exit(1)


@app.command("market-close")
def market_close(
    coin: Annotated[str, typer.Argument(help="Perp coin to close position")],
    size: Annotated[Optional[float], typer.Option(help="Partial close size (omit for full close)")] = None,
    slippage: Annotated[float, typer.Option(help="Slippage tolerance (0.01 = 1%%)")] = 0.01,
) -> None:
    """Market close a perp position (full or partial)."""
    client = get_client()
    try:
        result = client.exchange.market_close(coin, None, size, slippage)
        print_order_response(result)
    except Exception as e:
        console.print(f"[red]Market close failed:[/red] {e}")
        raise typer.Exit(1)


# ── TP / SL ────────────────────────────────────────────────


@app.command()
def tp(
    coin: Annotated[str, typer.Argument(help="Perp coin")],
    side: Annotated[str, typer.Argument(help="sell (to close long) or buy (to close short)")],
    size: Annotated[float, typer.Argument(help="Order size")],
    price: Annotated[float, typer.Argument(help="Limit price (worst-case fill price)")],
    trigger: Annotated[float, typer.Option(help="Trigger price for take profit")] = 0,
) -> None:
    """Place a take-profit order (reduce only)."""
    if trigger == 0:
        console.print("[red]--trigger is required for TP orders.[/red]")
        raise typer.Exit(1)
    is_buy = side.lower() in ("buy", "b")
    client = get_client()
    order_type = {"trigger": {"triggerPx": trigger, "isMarket": True, "tpsl": "tp"}}
    try:
        result = client.exchange.order(coin, is_buy, size, price, order_type, reduce_only=True)
        print_order_response(result)
    except Exception as e:
        console.print(f"[red]TP order failed:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def sl(
    coin: Annotated[str, typer.Argument(help="Perp coin")],
    side: Annotated[str, typer.Argument(help="sell (to close long) or buy (to close short)")],
    size: Annotated[float, typer.Argument(help="Order size")],
    price: Annotated[float, typer.Argument(help="Limit price (worst-case fill price)")],
    trigger: Annotated[float, typer.Option(help="Trigger price for stop loss")] = 0,
) -> None:
    """Place a stop-loss order (reduce only)."""
    if trigger == 0:
        console.print("[red]--trigger is required for SL orders.[/red]")
        raise typer.Exit(1)
    is_buy = side.lower() in ("buy", "b")
    client = get_client()
    order_type = {"trigger": {"triggerPx": trigger, "isMarket": True, "tpsl": "sl"}}
    try:
        result = client.exchange.order(coin, is_buy, size, price, order_type, reduce_only=True)
        print_order_response(result)
    except Exception as e:
        console.print(f"[red]SL order failed:[/red] {e}")
        raise typer.Exit(1)


# ── Leverage ────────────────────────────────────────────────


@app.command()
def leverage(
    coin: Annotated[str, typer.Argument(help="Perp coin, e.g. ETH")],
    value: Annotated[int, typer.Argument(help="Leverage multiplier, e.g. 10")],
    isolated: Annotated[bool, typer.Option("--isolated", help="Use isolated margin (default: cross)")] = False,
) -> None:
    """Set leverage for a perp coin."""
    client = get_client()
    is_cross = not isolated
    try:
        result = client.exchange.update_leverage(value, coin, is_cross)
        if result.get("status") == "ok":
            mode = "cross" if is_cross else "isolated"
            console.print(f"[green]Leverage set to {value}x ({mode}) for {coin}.[/green]")
        else:
            console.print(f"[red]Failed:[/red] {result}")
    except Exception as e:
        console.print(f"[red]Leverage update failed:[/red] {e}")
        raise typer.Exit(1)


# ── Cancel ──────────────────────────────────────────────────


@app.command()
def cancel(
    coin: Annotated[str, typer.Argument(help="Perp coin")],
    oid: Annotated[int, typer.Argument(help="Order ID to cancel")],
) -> None:
    """Cancel an open order by OID."""
    client = get_client()
    try:
        result = client.exchange.cancel(coin, oid)
        print_order_response(result)
    except Exception as e:
        console.print(f"[red]Cancel failed:[/red] {e}")
        raise typer.Exit(1)


@app.command("cancel-all")
def cancel_all(
    coin: Annotated[str, typer.Argument(help="Cancel all orders for this coin")],
) -> None:
    """Cancel all open perp orders for a coin."""
    client = get_client()
    try:
        open_orders = client.info.open_orders(client.address)
        matching = [o for o in open_orders if o.get("coin") == coin]
        if not matching:
            console.print(f"[yellow]No open orders for {coin}.[/yellow]")
            return
        cancel_reqs = [{"coin": coin, "oid": o["oid"]} for o in matching]
        result = client.exchange.bulk_cancel(cancel_reqs)
        print_order_response(result)
    except Exception as e:
        console.print(f"[red]Cancel-all failed:[/red] {e}")
        raise typer.Exit(1)


# ── Modify ──────────────────────────────────────────────────


@app.command()
def modify(
    oid: Annotated[int, typer.Argument(help="Order ID to modify")],
    coin: Annotated[str, typer.Argument(help="Perp coin")],
    side: Annotated[str, typer.Argument(help="buy or sell")],
    size: Annotated[float, typer.Argument(help="New order size")],
    price: Annotated[float, typer.Argument(help="New limit price")],
    tif: Annotated[str, typer.Option(help="Time in force: gtc, ioc, alo")] = "gtc",
) -> None:
    """Modify an existing order."""
    is_buy = side.lower() in ("buy", "b")
    client = get_client()
    order_type = {"limit": {"tif": _resolve_tif(tif)}}
    try:
        result = client.exchange.modify_order(oid, coin, is_buy, size, price, order_type)
        print_order_response(result)
    except Exception as e:
        console.print(f"[red]Modify failed:[/red] {e}")
        raise typer.Exit(1)


# ── Query Commands ──────────────────────────────────────────


@app.command()
def positions() -> None:
    """View open perp positions and account summary."""
    client = get_client()
    try:
        state = client.info.user_state(client.address)
        print_account_summary(state)
        print_positions(state)
    except Exception as e:
        console.print(f"[red]Failed to fetch positions:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def orders(
    coin: Annotated[Optional[str], typer.Argument(help="Filter by coin (optional)")] = None,
) -> None:
    """View open perp orders. Optionally filter by coin."""
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
