"""Hyperliquid trading CLI — root app."""

import typer
from typing_extensions import Annotated

from hyper_cli.client import get_client, get_info
from hyper_cli.display import (
    console,
    print_candles,
    print_funding_rates,
    print_mid_prices,
    print_order_book,
    print_and_require_success,
    print_order_status,
    print_price,
)
from hyper_cli.market import INTERVAL_MS, current_funding_ctx, find_mid, normalize_coin, normalize_dex, now_ms, perp_dexs_arg
from hyper_cli.spot import app as spot_app
from hyper_cli.perp import app as perp_app
from hyper_cli.account import app as account_app
from hyper_cli.algo import app as algo_app
from hyper_cli.feed import app as feed_app
from hyper_cli.validation import confirm_or_exit

app = typer.Typer(
    name="hyper",
    help="Hyperliquid trading CLI — trading, market data, backtesting, and real-time feeds",
    no_args_is_help=True,
)

app.add_typer(spot_app, name="spot")
app.add_typer(perp_app, name="perp")
app.add_typer(account_app, name="account")
app.add_typer(algo_app, name="algo")
app.add_typer(feed_app, name="feed")


# ── Shared Top-Level Commands ──────────────────────────────


@app.command()
def status(
    oid: Annotated[int, typer.Argument(help="Order ID to check")],
) -> None:
    """Check status of any order by OID."""
    client = get_client()
    try:
        result = client.info.query_order_by_oid(client.address, oid)
        print_order_status(result)
    except Exception as e:
        console.print(f"[red]Failed to query order:[/red] {e}")
        raise typer.Exit(1)


@app.command("cancel-all")
def cancel_all(
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Cancel ALL open orders (spot and perp)."""
    confirm_or_exit("Cancel ALL open orders across spot and perp?", yes)
    client = get_client()
    try:
        open_orders = client.info.open_orders(client.address)
        if not open_orders:
            console.print("[yellow]No open orders.[/yellow]")
            return
        cancel_reqs = [{"coin": o["coin"], "oid": o["oid"]} for o in open_orders]
        result = client.exchange.bulk_cancel(cancel_reqs)
        print_and_require_success(result)
        console.print(f"[green]Cancelled {len(cancel_reqs)} order(s).[/green]")
    except Exception as e:
        console.print(f"[red]Cancel-all failed:[/red] {e}")
        raise typer.Exit(1)


# ── Market Data Commands ───────────────────────────────────


@app.command()
def price(
    coin: Annotated[str, typer.Argument(help="Coin or spot pair, e.g. ETH or PURR/USDC")],
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Show the current mid price for a coin."""
    dex_name = normalize_dex(dex)
    try:
        info = get_info(perp_dexs=perp_dexs_arg(dex_name))
        mids = info.all_mids(dex_name)
        match = find_mid(mids, info.name_to_coin, coin, dex_name)
        if match is None:
            console.print(f"[red]No mid price found for {coin}.[/red]")
            raise typer.Exit(1)
        symbol, mid = match
        print_price(symbol, mid)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Failed to fetch price:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def prices(
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Show all current mid prices."""
    dex_name = normalize_dex(dex)
    try:
        info = get_info(perp_dexs=perp_dexs_arg(dex_name))
        mids = info.all_mids(dex_name)
        print_mid_prices(mids)
    except Exception as e:
        console.print(f"[red]Failed to fetch prices:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def book(
    coin: Annotated[str, typer.Argument(help="Coin or spot pair, e.g. ETH or PURR/USDC")],
    depth: Annotated[int, typer.Option("--depth", "-d", min=1, help="Number of price levels per side")] = 10,
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Show an order book snapshot."""
    dex_name = normalize_dex(dex)
    try:
        info = get_info(perp_dexs=perp_dexs_arg(dex_name))
        market = normalize_coin(info, coin, dex_name)
        snapshot = info.l2_snapshot(market)
        print_order_book(snapshot, depth)
    except KeyError:
        console.print(f"[red]Unknown market: {coin}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to fetch order book:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def candles(
    coin: Annotated[str, typer.Argument(help="Coin or spot pair, e.g. ETH or PURR/USDC")],
    interval: Annotated[str, typer.Argument(help="Interval, e.g. 1m, 5m, 1h, 1d")],
    limit: Annotated[int, typer.Option("--limit", "-n", min=1, help="Number of candles to request")] = 24,
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Show OHLCV candles."""
    interval_ms = INTERVAL_MS.get(interval)
    if interval_ms is None:
        allowed = ", ".join(INTERVAL_MS)
        console.print(f"[red]Invalid interval '{interval}'. Use one of: {allowed}[/red]")
        raise typer.Exit(1)

    end_ms = now_ms()
    start_ms = end_ms - interval_ms * limit
    dex_name = normalize_dex(dex)
    try:
        info = get_info(perp_dexs=perp_dexs_arg(dex_name))
        market = normalize_coin(info, coin, dex_name)
        data = info.candles_snapshot(market, interval, start_ms, end_ms)
        print_candles(data[-limit:], market, interval)
    except KeyError:
        console.print(f"[red]Unknown market: {coin}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to fetch candles:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def funding(
    coin: Annotated[str, typer.Argument(help="Perp coin, e.g. ETH or BTC")],
    hours: Annotated[int, typer.Option("--hours", "-h", min=1, help="Funding history lookback in hours")] = 24,
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Show current and historical funding rates for a perp coin."""
    end_ms = now_ms()
    start_ms = end_ms - hours * 60 * 60 * 1000
    dex_name = normalize_dex(dex)
    try:
        info = get_info(perp_dexs=perp_dexs_arg(dex_name))
        market = normalize_coin(info, coin, dex_name)
        current = current_funding_ctx(info, market)
        history = info.funding_history(market, start_ms, end_ms)
        print_funding_rates(market, current, history)
    except KeyError:
        console.print(f"[red]Unknown perp market: {coin}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to fetch funding rates:[/red] {e}")
        raise typer.Exit(1)
