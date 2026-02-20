"""Rich-based display helpers for CLI output."""

from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


def print_order_response(response: Any) -> None:
    """Format and print the response from an order/cancel/modify call."""
    status = response.get("status", "unknown")
    if status == "ok":
        rdata = response.get("response", {})
        if "data" in rdata and "statuses" in rdata["data"]:
            for s in rdata["data"]["statuses"]:
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
                    console.print(f"Response: {s}")
        else:
            console.print(f"[green]OK.[/green] {rdata}")
    else:
        console.print(f"[red]Failed:[/red] {response}")


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
        side = "[green]Buy[/green]" if o.get("side", "").upper() == "B" else "[red]Sell[/red]"
        table.add_row(
            str(o.get("oid", "")),
            o.get("coin", ""),
            side,
            o.get("sz", ""),
            o.get("limitPx", ""),
            o.get("timestamp", ""),
        )

    console.print(table)


def print_order_status(order: dict) -> None:
    """Format a single order status."""
    if not order or order.get("status") == "unknownOid":
        console.print("[yellow]Order not found.[/yellow]")
        return

    order_data = order.get("order", order)
    side_raw = order_data.get("side", "")
    side = "Buy" if side_raw.upper() == "B" else "Sell"

    console.print(f"  Coin:   {order_data.get('coin', 'N/A')}")
    console.print(f"  Side:   {side}")
    console.print(f"  Size:   {order_data.get('sz', 'N/A')}")
    console.print(f"  Price:  {order_data.get('limitPx', 'N/A')}")
    console.print(f"  Status: {order.get('status', 'N/A')}")


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
