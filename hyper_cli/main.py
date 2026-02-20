"""Hyperliquid trading CLI — root app."""

import typer
from typing_extensions import Annotated

from hyper_cli.client import get_client
from hyper_cli.display import console, print_order_response, print_order_status
from hyper_cli.spot import app as spot_app
from hyper_cli.perp import app as perp_app

app = typer.Typer(
    name="hyper",
    help="Hyperliquid trading CLI — spot and perpetual trading",
    no_args_is_help=True,
)

app.add_typer(spot_app, name="spot")
app.add_typer(perp_app, name="perp")


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
def cancel_all() -> None:
    """Cancel ALL open orders (spot and perp)."""
    client = get_client()
    try:
        open_orders = client.info.open_orders(client.address)
        if not open_orders:
            console.print("[yellow]No open orders.[/yellow]")
            return
        cancel_reqs = [{"coin": o["coin"], "oid": o["oid"]} for o in open_orders]
        result = client.exchange.bulk_cancel(cancel_reqs)
        print_order_response(result)
        console.print(f"[green]Cancelled {len(cancel_reqs)} order(s).[/green]")
    except Exception as e:
        console.print(f"[red]Cancel-all failed:[/red] {e}")
        raise typer.Exit(1)
