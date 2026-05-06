"""Perpetual trading commands."""

from typing import Optional

import typer
from typing_extensions import Annotated

from hyper_cli.client import get_client
from hyper_cli.display import (
    console,
    print_open_orders,
    print_and_require_success,
    print_order_status,
    print_positions,
    print_account_summary,
)
from hyper_cli.market import normalize_coin, normalize_dex
from hyper_cli.responses import parse_action_response
from hyper_cli.validation import confirm_or_exit, parse_side, require_at_most, require_positive, require_slippage

app = typer.Typer(help="Perpetual trading commands", no_args_is_help=True)

TIF_VALUES = {"gtc": "Gtc", "ioc": "Ioc", "alo": "Alo"}


def _resolve_tif(tif: str) -> str:
    val = TIF_VALUES.get(tif.lower())
    if val is None:
        console.print(f"[red]Invalid TIF '{tif}'. Use: gtc, ioc, alo[/red]")
        raise typer.Exit(1)
    return val


def _exchange(client, dex: str):
    if dex and hasattr(client, "exchange_for_dex"):
        return client.exchange_for_dex(dex)
    return client.exchange


def _info(client, dex: str):
    if dex and hasattr(client, "info_for_dex"):
        return client.info_for_dex(dex)
    return client.info


def _market(client, coin: str, dex: str) -> str:
    if not dex:
        return coin
    return normalize_coin(_info(client, dex), coin, dex)


# ── Long / Short (Limit) ───────────────────────────────────


@app.command()
def long(
    coin: Annotated[str, typer.Argument(help="Perp coin, e.g. ETH, BTC")],
    size: Annotated[float, typer.Argument(help="Order size")],
    price: Annotated[float, typer.Argument(help="Limit price")],
    tif: Annotated[str, typer.Option(help="Time in force: gtc, ioc, alo")] = "gtc",
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Place a limit long (buy) order."""
    require_positive("size", size)
    require_positive("price", price)
    client = get_client()
    dex_name = normalize_dex(dex)
    market = _market(client, coin, dex_name)
    order_type = {"limit": {"tif": _resolve_tif(tif)}}
    try:
        result = _exchange(client, dex_name).order(market, True, size, price, order_type)
        print_and_require_success(result)
    except Exception as e:
        console.print(f"[red]Long order failed:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def short(
    coin: Annotated[str, typer.Argument(help="Perp coin, e.g. ETH, BTC")],
    size: Annotated[float, typer.Argument(help="Order size")],
    price: Annotated[float, typer.Argument(help="Limit price")],
    tif: Annotated[str, typer.Option(help="Time in force: gtc, ioc, alo")] = "gtc",
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Place a limit short (sell) order."""
    require_positive("size", size)
    require_positive("price", price)
    client = get_client()
    dex_name = normalize_dex(dex)
    market = _market(client, coin, dex_name)
    order_type = {"limit": {"tif": _resolve_tif(tif)}}
    try:
        result = _exchange(client, dex_name).order(market, False, size, price, order_type)
        print_and_require_success(result)
    except Exception as e:
        console.print(f"[red]Short order failed:[/red] {e}")
        raise typer.Exit(1)


# ── Market Orders ───────────────────────────────────────────


@app.command("market-open")
def market_open(
    coin: Annotated[str, typer.Argument(help="Perp coin, e.g. ETH")],
    side: Annotated[str, typer.Argument(help="buy or sell")],
    size: Annotated[float, typer.Argument(help="Order size")],
    slippage: Annotated[
        float,
        typer.Option(min=0.0, max=1.0, help="Slippage tolerance (0.01 = 1%)"),
    ] = 0.01,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print the action without signing or placing an order")] = False,
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Market open a perp position."""
    require_positive("size", size)
    require_slippage("slippage", slippage)
    is_buy = parse_side(side)
    client = get_client()
    dex_name = normalize_dex(dex)
    market = _market(client, coin, dex_name)
    side_label = "buy" if is_buy else "sell"
    console.print(f"[yellow]Preview:[/yellow] perp market {side_label} {size} {market} with slippage {slippage}")
    if dry_run:
        return
    confirm_or_exit(f"Place perp market {side_label} order for {size} {market}?", yes)
    try:
        result = _exchange(client, dex_name).market_open(market, is_buy, size, None, slippage)
        print_and_require_success(result)
    except Exception as e:
        console.print(f"[red]Market open failed:[/red] {e}")
        raise typer.Exit(1)


@app.command("market-close")
def market_close(
    coin: Annotated[str, typer.Argument(help="Perp coin to close position")],
    size: Annotated[Optional[float], typer.Option(help="Partial close size (omit for full close)")] = None,
    slippage: Annotated[
        float,
        typer.Option(min=0.0, max=1.0, help="Slippage tolerance (0.01 = 1%)"),
    ] = 0.01,
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Market close a perp position (full or partial)."""
    if size is not None:
        require_positive("size", size)
    require_slippage("slippage", slippage)
    client = get_client()
    dex_name = normalize_dex(dex)
    market = _market(client, coin, dex_name)
    try:
        result = _exchange(client, dex_name).market_close(market, sz=size, slippage=slippage)
        if result is None:
            console.print(f"[yellow]No open position found for {market}.[/yellow]")
            return
        print_and_require_success(result)
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
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Place a take-profit order (reduce only)."""
    require_positive("size", size)
    require_positive("price", price)
    require_positive("trigger", trigger)
    is_buy = parse_side(side, allow_position_aliases=False)
    client = get_client()
    dex_name = normalize_dex(dex)
    market = _market(client, coin, dex_name)
    order_type = {"trigger": {"triggerPx": trigger, "isMarket": True, "tpsl": "tp"}}
    try:
        result = _exchange(client, dex_name).order(market, is_buy, size, price, order_type, reduce_only=True)
        print_and_require_success(result)
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
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Place a stop-loss order (reduce only)."""
    require_positive("size", size)
    require_positive("price", price)
    require_positive("trigger", trigger)
    is_buy = parse_side(side, allow_position_aliases=False)
    client = get_client()
    dex_name = normalize_dex(dex)
    market = _market(client, coin, dex_name)
    order_type = {"trigger": {"triggerPx": trigger, "isMarket": True, "tpsl": "sl"}}
    try:
        result = _exchange(client, dex_name).order(market, is_buy, size, price, order_type, reduce_only=True)
        print_and_require_success(result)
    except Exception as e:
        console.print(f"[red]SL order failed:[/red] {e}")
        raise typer.Exit(1)


# ── Leverage ────────────────────────────────────────────────


@app.command()
def leverage(
    coin: Annotated[str, typer.Argument(help="Perp coin, e.g. ETH")],
    value: Annotated[int, typer.Argument(min=1, max=50, help="Leverage multiplier, e.g. 10")],
    isolated: Annotated[bool, typer.Option("--isolated", help="Use isolated margin (default: cross)")] = False,
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Set leverage for a perp coin."""
    require_positive("value", value)
    require_at_most("value", value, 50)
    client = get_client()
    dex_name = normalize_dex(dex)
    market = _market(client, coin, dex_name)
    is_cross = not isolated
    try:
        result = _exchange(client, dex_name).update_leverage(value, market, is_cross)
        summary = parse_action_response(result)
        if summary.ok:
            mode = "cross" if is_cross else "isolated"
            console.print(f"[green]Leverage set to {value}x ({mode}) for {market}.[/green]")
        else:
            console.print(f"[red]Failed:[/red] {result}")
            raise RuntimeError("; ".join(summary.errors) or "Leverage update failed")
    except Exception as e:
        console.print(f"[red]Leverage update failed:[/red] {e}")
        raise typer.Exit(1)


# ── Cancel ──────────────────────────────────────────────────


@app.command()
def cancel(
    coin: Annotated[str, typer.Argument(help="Perp coin")],
    oid: Annotated[int, typer.Argument(help="Order ID to cancel")],
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Cancel an open order by OID."""
    client = get_client()
    dex_name = normalize_dex(dex)
    market = _market(client, coin, dex_name)
    try:
        result = _exchange(client, dex_name).cancel(market, oid)
        print_and_require_success(result)
    except Exception as e:
        console.print(f"[red]Cancel failed:[/red] {e}")
        raise typer.Exit(1)


@app.command("cancel-all")
def cancel_all(
    coin: Annotated[str, typer.Argument(help="Cancel all orders for this coin")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Cancel all open perp orders for a coin."""
    client = get_client()
    dex_name = normalize_dex(dex)
    market = _market(client, coin, dex_name)
    confirm_or_exit(f"Cancel all open perp orders for {market}?", yes)
    try:
        open_orders = _info(client, dex_name).open_orders(client.address, dex=dex_name)
        matching = [o for o in open_orders if o.get("coin") == market]
        if not matching:
            console.print(f"[yellow]No open orders for {market}.[/yellow]")
            return
        cancel_reqs = [{"coin": market, "oid": o["oid"]} for o in matching]
        result = _exchange(client, dex_name).bulk_cancel(cancel_reqs)
        print_and_require_success(result)
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
    reduce_only: Annotated[
        Optional[bool],
        typer.Option("--reduce-only/--not-reduce-only", help="Required explicit reduce-only mode for the replacement order"),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print the replacement order without signing")] = False,
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Modify an existing order."""
    require_positive("size", size)
    require_positive("price", price)
    if reduce_only is None:
        console.print("[red]perp modify requires --reduce-only or --not-reduce-only.[/red]")
        raise typer.Exit(1)
    is_buy = parse_side(side, allow_position_aliases=False)
    client = get_client()
    dex_name = normalize_dex(dex)
    market = _market(client, coin, dex_name)
    order_type = {"limit": {"tif": _resolve_tif(tif)}}
    side_label = "buy" if is_buy else "sell"
    console.print(
        f"[yellow]Preview:[/yellow] modify OID {oid}: {side_label} {size} {market} at {price}, "
        f"tif={tif}, reduce_only={reduce_only}"
    )
    if dry_run:
        return
    confirm_or_exit(f"Modify perp order {oid} on {market}?", yes)
    try:
        result = _exchange(client, dex_name).modify_order(
            oid,
            market,
            is_buy,
            size,
            price,
            order_type,
            reduce_only=reduce_only,
        )
        print_and_require_success(result)
    except Exception as e:
        console.print(f"[red]Modify failed:[/red] {e}")
        raise typer.Exit(1)


# ── Query Commands ──────────────────────────────────────────


@app.command()
def positions(
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """View open perp positions and account summary."""
    client = get_client()
    dex_name = normalize_dex(dex)
    try:
        state = _info(client, dex_name).user_state(client.address, dex=dex_name)
        print_account_summary(state)
        print_positions(state)
    except Exception as e:
        console.print(f"[red]Failed to fetch positions:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def orders(
    coin: Annotated[Optional[str], typer.Argument(help="Filter by coin (optional)")] = None,
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """View open perp orders. Optionally filter by coin."""
    client = get_client()
    dex_name = normalize_dex(dex)
    try:
        all_orders = _info(client, dex_name).open_orders(client.address, dex=dex_name)
        if coin:
            market = _market(client, coin, dex_name)
            all_orders = [o for o in all_orders if o.get("coin") == market]
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
