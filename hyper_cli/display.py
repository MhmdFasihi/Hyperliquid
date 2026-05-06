"""Rich-based display helpers for CLI output."""

import datetime
from typing import Any

from rich.console import Console
from rich.table import Table

from hyper_cli.responses import ActionSummary, parse_action_response

console = Console()


def print_order_response(response: Any) -> ActionSummary:
    """Format and print the response from an order/cancel/modify call."""
    summary = parse_action_response(response)
    if response is None:
        console.print("[yellow]No response returned.[/yellow]")
        return summary
    if not isinstance(response, dict):
        console.print(f"[yellow]Unexpected response:[/yellow] {response}")
        return summary

    status = response.get("status", "unknown")
    if status == "ok":
        rdata = response.get("response", {})
        data = rdata.get("data") if isinstance(rdata, dict) else None
        statuses = data.get("statuses") if isinstance(data, dict) else None
        if isinstance(statuses, list):
            for s in statuses:
                if s == "success":
                    console.print("[green]Success.[/green]")
                    continue
                if not isinstance(s, dict):
                    console.print(f"[yellow]Unknown response:[/yellow] {s}")
                    continue
                if "resting" in s:
                    oid = s["resting"]["oid"]
                    console.print(f"[green]Order placed.[/green] OID: [bold]{oid}[/bold]")
                elif "filled" in s:
                    fill = s["filled"]
                    console.print(
                        f"[green]Order filled.[/green] "
                        f"Avg price: {fill.get('avgPx', 'N/A')}, "
                        f"Total size: {fill.get('totalSz', 'N/A')}"
                    )
                elif "error" in s:
                    console.print(f"[red]Error:[/red] {s['error']}")
                else:
                    console.print(f"[yellow]Unknown response:[/yellow] {s}")
        elif isinstance(data, dict) and data.get("status") is not None:
            status_item = data["status"]
            if status_item == "success":
                console.print("[green]Success.[/green]")
            elif isinstance(status_item, dict) and "error" in status_item:
                console.print(f"[red]Error:[/red] {status_item['error']}")
            else:
                console.print(f"[yellow]Unknown response:[/yellow] {status_item}")
        else:
            console.print(f"[green]OK.[/green] {rdata}")
    else:
        console.print(f"[red]Failed:[/red] {response}")
    return summary


def print_and_require_success(response: Any) -> ActionSummary:
    summary = print_order_response(response)
    if not summary.ok:
        raise RuntimeError("; ".join(summary.errors) or "Action failed")
    return summary


def print_balances(state: dict) -> None:
    """Format spot_user_state into a table."""
    balances = state.get("balances", [])
    if not balances:
        console.print("[yellow]No spot balances found.[/yellow]")
        return

    table = Table(title="Spot Balances")
    table.add_column("Token", style="cyan")
    table.add_column("Hold", justify="right")
    table.add_column("Total", justify="right", style="green")
    table.add_column("Entry Notional", justify="right")

    for b in balances:
        table.add_row(
            b.get("coin", "?"),
            b.get("hold", "0"),
            b.get("total", "0"),
            b.get("entryNtl", "0"),
        )

    console.print(table)


def print_open_orders(orders: list) -> None:
    """Format open orders into a table."""
    if not orders:
        console.print("[yellow]No open orders.[/yellow]")
        return

    table = Table(title="Open Orders")
    table.add_column("OID", style="cyan")
    table.add_column("Coin")
    table.add_column("Side")
    table.add_column("Size", justify="right")
    table.add_column("Price", justify="right", style="green")
    table.add_column("Timestamp")

    for o in orders:
        side = format_side(o.get("side"))
        table.add_row(
            str(o.get("oid", "")),
            o.get("coin", ""),
            side,
            o.get("sz", ""),
            o.get("limitPx", ""),
            format_time_ms(o.get("timestamp")),
        )

    console.print(table)


def print_order_status(order: dict) -> None:
    """Format a single order status."""
    if not order or order.get("status") == "unknownOid":
        console.print("[yellow]Order not found.[/yellow]")
        return

    order_data = order.get("order", order)
    side_raw = order_data.get("side", "")
    side = format_side(side_raw, plain=True)

    console.print(f"  Coin:   {order_data.get('coin', 'N/A')}")
    console.print(f"  Side:   {side}")
    console.print(f"  Size:   {order_data.get('sz', 'N/A')}")
    console.print(f"  Price:  {order_data.get('limitPx', 'N/A')}")
    console.print(f"  Status: {order.get('status', 'N/A')}")


# ── Market Data Display ────────────────────────────────────


def format_time_ms(ts_ms: Any) -> str:
    if ts_ms in (None, ""):
        return "N/A"
    try:
        dt = datetime.datetime.fromtimestamp(int(ts_ms) / 1000, tz=datetime.timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (TypeError, ValueError, OSError):
        return str(ts_ms)


def format_side(raw: Any, plain: bool = False) -> str:
    value = str(raw or "").upper()
    if value == "B":
        return "Buy" if plain else "[green]Buy[/green]"
    if value == "A":
        return "Sell" if plain else "[red]Sell[/red]"
    return f"Unknown ({raw})" if raw not in (None, "") else "Unknown"


def _format_percent(value: Any) -> str:
    if value in (None, ""):
        return "N/A"
    try:
        return f"{float(value) * 100:.5f}%"
    except (TypeError, ValueError):
        return str(value)


def print_price(coin: str, price: Any) -> None:
    """Print a single mid price."""
    console.print(f"[bold cyan]{coin}[/bold cyan] mid: [green]{price}[/green]")


def print_mid_prices(mids: dict) -> None:
    """Format all mid prices into a table."""
    if not mids:
        console.print("[yellow]No mid prices found.[/yellow]")
        return

    table = Table(title="Mid Prices")
    table.add_column("Coin", style="cyan")
    table.add_column("Mid", justify="right", style="green")

    for coin, price in sorted(mids.items()):
        table.add_row(str(coin), str(price))

    console.print(table)


def print_order_book(snapshot: dict, depth: int) -> None:
    """Format an L2 order book snapshot."""
    levels = snapshot.get("levels", [])
    bids = levels[0] if len(levels) > 0 else []
    asks = levels[1] if len(levels) > 1 else []

    if not bids and not asks:
        console.print("[yellow]No order book levels found.[/yellow]")
        return

    coin = snapshot.get("coin", "Order Book")
    table = Table(title=f"{coin} Order Book ({format_time_ms(snapshot.get('time'))})")
    table.add_column("Bid Orders", justify="right")
    table.add_column("Bid Size", justify="right")
    table.add_column("Bid Price", justify="right", style="green")
    table.add_column("Ask Price", justify="right", style="red")
    table.add_column("Ask Size", justify="right")
    table.add_column("Ask Orders", justify="right")

    row_count = min(depth, max(len(bids), len(asks)))
    for idx in range(row_count):
        bid = bids[idx] if idx < len(bids) else {}
        ask = asks[idx] if idx < len(asks) else {}
        table.add_row(
            str(bid.get("n", "")),
            str(bid.get("sz", "")),
            str(bid.get("px", "")),
            str(ask.get("px", "")),
            str(ask.get("sz", "")),
            str(ask.get("n", "")),
        )

    console.print(table)


def print_candles(candles: list, coin: str, interval: str) -> None:
    """Format OHLCV candles into a table."""
    if not candles:
        console.print(f"[yellow]No candles found for {coin} {interval}.[/yellow]")
        return

    table = Table(title=f"{coin} Candles ({interval})")
    table.add_column("Open Time", style="cyan")
    table.add_column("Open", justify="right")
    table.add_column("High", justify="right", style="green")
    table.add_column("Low", justify="right", style="red")
    table.add_column("Close", justify="right")
    table.add_column("Volume", justify="right")
    table.add_column("Trades", justify="right")

    for candle in candles:
        table.add_row(
            format_time_ms(candle.get("t")),
            str(candle.get("o", "")),
            str(candle.get("h", "")),
            str(candle.get("l", "")),
            str(candle.get("c", "")),
            str(candle.get("v", "")),
            str(candle.get("n", "")),
        )

    console.print(table)


def print_funding_rates(coin: str, current: dict | None, history: list) -> None:
    """Format current and historical funding rates."""
    if current:
        console.print(f"[bold]{coin} Current Funding[/bold]")
        console.print(f"  Funding:  {_format_percent(current.get('funding'))}")
        console.print(f"  Premium:  {_format_percent(current.get('premium'))}")
        console.print(f"  Oracle:   {current.get('oraclePx', 'N/A')}")
        console.print(f"  Mark:     {current.get('markPx', 'N/A')}")
        console.print()

    if not history:
        console.print(f"[yellow]No funding history found for {coin}.[/yellow]")
        return

    table = Table(title=f"{coin} Funding History")
    table.add_column("Time", style="cyan")
    table.add_column("Funding Rate", justify="right", style="green")
    table.add_column("Premium", justify="right")

    for item in history:
        table.add_row(
            format_time_ms(item.get("time")),
            _format_percent(item.get("fundingRate")),
            _format_percent(item.get("premium")),
        )

    console.print(table)


# ── Algo Framework Display ─────────────────────────────────


def print_signal(signal: Any) -> None:
    """Format one strategy signal."""
    table = Table(title="Strategy Signal")
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    table.add_row("Action", str(signal.action.value).upper())
    table.add_row("Coin", signal.coin)
    table.add_row("Size", str(signal.size))
    table.add_row("Price", "market" if signal.price is None else str(signal.price))
    table.add_row("Order Type", signal.order_type)
    table.add_row("Reason", signal.reason or "N/A")

    console.print(table)


def print_strategy_catalog(strategies: dict) -> None:
    """Format available strategies and required params."""
    table = Table(title="Built-in Strategies")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Params")

    for name, cls in sorted(strategies.items()):
        params = ", ".join(cls.parameter_help)
        table.add_row(name, cls.description, params)

    console.print(table)


def print_backtest_result(result: Any, max_trades: int = 10) -> None:
    """Format backtest summary and recent trades."""
    summary = Table(title=f"{result.coin} Backtest ({result.interval})")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", justify="right")

    summary.add_row("Starting Equity", f"${result.starting_equity:,.2f}")
    summary.add_row("Final Equity", f"${result.final_equity:,.2f}")
    summary.add_row("PnL", f"${result.pnl:,.2f}")
    summary.add_row("Return", f"{result.return_pct:.2f}%")
    summary.add_row("Max Drawdown", f"{result.max_drawdown_pct:.2f}%")
    summary.add_row("Final Cash", f"${result.final_cash:,.2f}")
    summary.add_row("Final Position", f"{result.final_position:.8g}")
    summary.add_row("Trades", str(len(result.trades)))
    summary.add_row("Skipped Signals", str(result.skipped_signals))
    summary.add_row("Fees", f"${result.total_fees:,.2f}")

    console.print(summary)

    if not result.trades:
        console.print("[yellow]No trades executed.[/yellow]")
        return

    trades = Table(title=f"Last {min(max_trades, len(result.trades))} Trade(s)")
    trades.add_column("Time", style="cyan")
    trades.add_column("Side")
    trades.add_column("Size", justify="right")
    trades.add_column("Price", justify="right")
    trades.add_column("Fee", justify="right")
    trades.add_column("Equity Cash", justify="right")
    trades.add_column("Position", justify="right")

    for trade in result.trades[-max_trades:]:
        trades.add_row(
            format_time_ms(trade.time_ms),
            trade.action.value.upper(),
            f"{trade.size:.8g}",
            f"{trade.price:.8g}",
            f"${trade.fee:,.4f}",
            f"${trade.cash:,.2f}",
            f"{trade.position:.8g}",
        )

    console.print(trades)


# ── Account Management Display ─────────────────────────────


def print_ledger_history(updates: list, days: int) -> None:
    """Format non-funding ledger updates (deposits, withdrawals, transfers)."""
    if not updates:
        console.print(f"[yellow]No transactions in the last {days} day(s).[/yellow]")
        return

    table = Table(title=f"Transaction History (last {days} day(s))")
    table.add_column("Time", style="cyan")
    table.add_column("Type")
    table.add_column("Amount", justify="right", style="green")
    table.add_column("Details")

    for entry in updates:
        ts_ms = entry.get("time", 0)
        dt = datetime.datetime.fromtimestamp(ts_ms / 1000, tz=datetime.timezone.utc)
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")

        delta = entry.get("delta", {})
        entry_type = delta.get("type", "unknown")

        usdc = delta.get("usdc", None)
        amount_str = f"${usdc}" if usdc is not None else "—"

        skip = {"type", "usdc"}
        details = ", ".join(f"{k}={v}" for k, v in delta.items() if k not in skip)

        table.add_row(time_str, entry_type, amount_str, details)

    console.print(table)


def print_sub_accounts(accounts: list) -> None:
    """Format sub-account list into a table."""
    if not accounts:
        console.print("[yellow]No sub-accounts found.[/yellow]")
        return

    table = Table(title="Sub-Accounts")
    table.add_column("Name", style="cyan")
    table.add_column("Address")
    table.add_column("Account Value", justify="right", style="green")
    table.add_column("Withdrawable", justify="right")

    for acct in accounts:
        margin = acct.get("clearinghouseState", {}).get("marginSummary", {})
        table.add_row(
            acct.get("name", "—"),
            acct.get("subAccountUser", "—"),
            f"${margin.get('accountValue', 'N/A')}",
            f"${acct.get('clearinghouseState', {}).get('withdrawable', 'N/A')}",
        )

    console.print(table)


# ── Perp-Specific Display ──────────────────────────────────


def print_account_summary(state: dict) -> None:
    """Print perp account margin summary."""
    margin = state.get("marginSummary") or state.get("crossMarginSummary", {})
    if not margin:
        console.print("[yellow]No margin data available.[/yellow]")
        return

    console.print()
    console.print("[bold]Account Summary[/bold]")
    console.print(f"  Account Value:  ${margin.get('accountValue', 'N/A')}")
    console.print(f"  Total Margin:   ${margin.get('totalMarginUsed', 'N/A')}")
    console.print(f"  Total NtlPos:   ${margin.get('totalNtlPos', 'N/A')}")
    console.print(f"  Total Raw Usd:  ${margin.get('totalRawUsd', 'N/A')}")
    withdrawable = state.get("withdrawable", "N/A")
    console.print(f"  Withdrawable:   ${withdrawable}")
    console.print()


def print_positions(state: dict) -> None:
    """Format perp positions into a table."""
    asset_positions = state.get("assetPositions", [])
    positions = [ap["position"] for ap in asset_positions if float(ap["position"].get("szi", 0)) != 0]

    if not positions:
        console.print("[yellow]No open positions.[/yellow]")
        return

    table = Table(title="Open Positions")
    table.add_column("Coin", style="cyan")
    table.add_column("Side")
    table.add_column("Size", justify="right")
    table.add_column("Entry Price", justify="right")
    table.add_column("Unrealized PnL", justify="right")
    table.add_column("Leverage", justify="right")
    table.add_column("Liq. Price", justify="right", style="red")
    table.add_column("Margin Used", justify="right")

    for p in positions:
        szi = float(p.get("szi", 0))
        side = "[green]Long[/green]" if szi > 0 else "[red]Short[/red]"
        size_str = str(abs(szi))

        pnl = p.get("unrealizedPnl", "0")
        pnl_val = float(pnl)
        pnl_style = "[green]" if pnl_val >= 0 else "[red]"
        pnl_str = f"{pnl_style}${pnl}[/{pnl_style.strip('[')}]"

        leverage_info = p.get("leverage", {})
        lev_val = leverage_info.get("value", "N/A")
        lev_type = leverage_info.get("type", "")
        lev_str = f"{lev_val}x {lev_type}"

        table.add_row(
            p.get("coin", "?"),
            side,
            size_str,
            p.get("entryPx", "N/A"),
            pnl_str,
            lev_str,
            p.get("liquidationPx", "N/A"),
            p.get("marginUsed", "N/A"),
        )

    console.print(table)
