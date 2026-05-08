"""Real-time WebSocket feed commands."""

import datetime
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

import typer
from rich.table import Table
from typing_extensions import Annotated

from hyper_cli.client import get_client, get_ws_info
from hyper_cli.display import console, format_side, format_time_ms, print_order_book, print_signal
from hyper_cli.market import find_mid, normalize_coin, normalize_dex, perp_dexs_arg
from hyper_cli.strategies import (
    MarketSnapshot,
    Signal,
    SignalAction,
    StrategyConfigError,
    StrategyState,
    build_strategy,
    load_strategy_config,
)
from hyper_cli.validation import require_non_negative, require_positive, require_slippage

app = typer.Typer(help="Real-time WebSocket feed commands", no_args_is_help=True)


class StreamController:
    def __init__(self, updates: int | None):
        self.updates = updates
        self.count = 0
        self.error: BaseException | None = None
        self.changed = threading.Event()
        self.done = threading.Event()
        self.lock = threading.Lock()

    def tick(self) -> None:
        with self.lock:
            self.count += 1
            if self.updates is not None and self.count >= self.updates:
                self.done.set()
            self.changed.set()

    def fail(self, error: BaseException) -> None:
        with self.lock:
            self.error = error
            self.done.set()
            self.changed.set()


@app.command()
def prices(
    coins: Annotated[
        Optional[str],
        typer.Option("--coins", "-c", help="Comma-separated coins to print. Defaults to BTC,ETH,SOL."),
    ] = None,
    all_markets: Annotated[bool, typer.Option("--all", help="Print every received mid price.")] = False,
    seconds: Annotated[Optional[int], typer.Option("--seconds", "-s", min=1, help="Stop after N seconds")] = None,
    updates: Annotated[Optional[int], typer.Option("--updates", "-n", min=1, help="Stop after N updates")] = None,
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Stream live mid prices."""
    dex_name = normalize_dex(dex)
    selected = [] if all_markets else _parse_csv(coins) or ["BTC", "ETH", "SOL"]
    controller = StreamController(updates)
    info = None

    def on_msg(msg: dict) -> None:
        try:
            mids = msg.get("data", {}).get("mids", {})
            if selected:
                rows = []
                for coin in selected:
                    match = find_mid(mids, info.name_to_coin, coin, dex_name)
                    if match is not None:
                        rows.append(match)
            else:
                rows = sorted(mids.items())

            if rows:
                _print_price_rows(rows)
            controller.tick()
        except Exception as exc:
            controller.fail(exc)

    try:
        info = get_ws_info(perp_dexs=perp_dexs_arg(dex_name))
        subscription: dict[str, str] = {"type": "allMids"}
        if dex_name:
            subscription["dex"] = dex_name
        info.subscribe(subscription, on_msg)
        _wait_for_stream(info, controller, seconds)
    except Exception as e:
        console.print(f"[red]Price feed failed:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def book(
    coin: Annotated[str, typer.Argument(help="Coin or spot pair, e.g. ETH or PURR/USDC")],
    depth: Annotated[int, typer.Option("--depth", "-d", min=1, help="Number of price levels per side")] = 5,
    seconds: Annotated[Optional[int], typer.Option("--seconds", "-s", min=1, help="Stop after N seconds")] = None,
    updates: Annotated[Optional[int], typer.Option("--updates", "-n", min=1, help="Stop after N updates")] = None,
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Stream live order book updates."""
    dex_name = normalize_dex(dex)
    controller = StreamController(updates)

    def on_msg(msg: dict) -> None:
        try:
            print_order_book(msg.get("data", {}), depth)
            controller.tick()
        except Exception as exc:
            controller.fail(exc)

    try:
        info = get_ws_info(perp_dexs=perp_dexs_arg(dex_name))
        market = normalize_coin(info, coin, dex_name)
        info.subscribe({"type": "l2Book", "coin": market}, on_msg)
        _wait_for_stream(info, controller, seconds)
    except KeyError:
        console.print(f"[red]Unknown market: {coin}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Book feed failed:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def trades(
    coin: Annotated[str, typer.Argument(help="Coin or spot pair, e.g. ETH or PURR/USDC")],
    seconds: Annotated[Optional[int], typer.Option("--seconds", "-s", min=1, help="Stop after N seconds")] = None,
    updates: Annotated[Optional[int], typer.Option("--updates", "-n", min=1, help="Stop after N messages")] = None,
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Stream live trades."""
    dex_name = normalize_dex(dex)
    controller = StreamController(updates)

    def on_msg(msg: dict) -> None:
        try:
            _print_trades(msg.get("data", []))
            controller.tick()
        except Exception as exc:
            controller.fail(exc)

    try:
        info = get_ws_info(perp_dexs=perp_dexs_arg(dex_name))
        market = normalize_coin(info, coin, dex_name)
        info.subscribe({"type": "trades", "coin": market}, on_msg)
        _wait_for_stream(info, controller, seconds)
    except KeyError:
        console.print(f"[red]Unknown market: {coin}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Trade feed failed:[/red] {e}")
        raise typer.Exit(1)


@app.command("account")
def account_events(
    seconds: Annotated[Optional[int], typer.Option("--seconds", "-s", min=1, help="Stop after N seconds")] = None,
    updates: Annotated[Optional[int], typer.Option("--updates", "-n", min=1, help="Stop after N events")] = None,
    events: Annotated[bool, typer.Option("--events", help="Subscribe to user events")] = False,
    orders: Annotated[bool, typer.Option("--orders", help="Subscribe to order updates")] = False,
    fills: Annotated[bool, typer.Option("--fills", help="Subscribe to user fills")] = False,
    include_snapshots: Annotated[bool, typer.Option("--include-snapshots", help="Count and print snapshot messages")] = False,
) -> None:
    """Stream account fills and order updates for the configured account."""
    controller = StreamController(updates)
    if not any((events, orders, fills)):
        events = orders = fills = True

    def make_callback(label: str) -> Callable[[dict], None]:
        def on_msg(msg: dict) -> None:
            try:
                data = msg.get("data", msg)
                if not include_snapshots and isinstance(data, dict) and data.get("isSnapshot"):
                    return
                console.print(f"[bold cyan]{label}[/bold cyan] {_utc_now()}")
                console.print(json.dumps(data, indent=2))
                controller.tick()
            except Exception as exc:
                controller.fail(exc)

        return on_msg

    try:
        client = get_client()
        info = get_ws_info()
        if events:
            info.subscribe({"type": "userEvents", "user": client.address}, make_callback("User Event"))
        if orders:
            info.subscribe({"type": "orderUpdates", "user": client.address}, make_callback("Order Update"))
        if fills:
            info.subscribe({"type": "userFills", "user": client.address}, make_callback("User Fills"))
        _wait_for_stream(info, controller, seconds)
    except Exception as e:
        console.print(f"[red]Account feed failed:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def strategy(
    config: Annotated[Path, typer.Argument(help="Strategy config file (.json, .yaml, .yml)")],
    seconds: Annotated[Optional[int], typer.Option("--seconds", "-s", min=1, help="Stop after N seconds")] = None,
    updates: Annotated[Optional[int], typer.Option("--updates", "-n", min=1, help="Stop after N processed candles")] = None,
    position: Annotated[float, typer.Option("--position", min=0.0, help="Initial local base-asset position")] = 0.0,
    step: Annotated[int, typer.Option("--step", min=0, help="Initial strategy step index")] = 0,
    every_update: Annotated[bool, typer.Option("--every-update", help="Process every candle update, not just new candles")] = False,
    execute: Annotated[bool, typer.Option("--execute", help="Disabled; exits before placing live orders")] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Reserved for future execution support")] = False,
    slippage: Annotated[
        float,
        typer.Option("--slippage", min=0.0, max=1.0, help="Reserved execution slippage setting"),
    ] = 0.01,
    max_orders: Annotated[Optional[int], typer.Option("--max-orders", min=1, help="Reserved for future execution support")] = None,
    max_notional: Annotated[Optional[float], typer.Option("--max-notional", min=0.0, help="Reserved for future execution support")] = None,
    max_position: Annotated[Optional[float], typer.Option("--max-position", min=0.0, help="Reserved for future execution support")] = None,
    cooldown_seconds: Annotated[float, typer.Option("--cooldown-seconds", min=0.0, help="Reserved for future execution support")] = 0.0,
    dex: Annotated[str, typer.Option("--dex", help="Perp DEX name for builder-deployed markets")] = "",
) -> None:
    """Run a strategy from live candle WebSocket triggers."""
    if execute:
        console.print("[red]feed strategy --execute is disabled in this release. Run without --execute for dry-run signals.[/red]")
        raise typer.Exit(1)

    require_slippage("slippage", slippage)
    require_non_negative("position", position)
    require_non_negative("cooldown_seconds", cooldown_seconds)
    if max_orders is not None:
        require_positive("max_orders", max_orders)
    if max_notional is not None:
        require_non_negative("max_notional", max_notional)
    if max_position is not None:
        require_non_negative("max_position", max_position)
    dex_name = normalize_dex(dex)

    try:
        cfg = load_strategy_config(config)
        strat = build_strategy(cfg)
        info = get_ws_info(perp_dexs=perp_dexs_arg(dex_name))
        market = normalize_coin(info, cfg.coin, dex_name)
    except StrategyConfigError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to initialize strategy feed:[/red] {e}")
        raise typer.Exit(1)

    controller = StreamController(updates)
    state = StrategyState(position=position, step=step)

    def on_msg(msg: dict) -> None:
        try:
            incoming = msg.get("data", {})
            if every_update:
                candle = incoming
            else:
                candle = state.metadata.get("pending_candle")
                state.metadata["pending_candle"] = incoming
                if candle is None or candle.get("t") == incoming.get("t"):
                    return

            price = float(candle["c"])
            snapshot = MarketSnapshot(cfg.coin, price, candle.get("t"), candle)
            sig = strat.generate_signal(snapshot, state)
            print_signal(sig)

            _apply_local_position(state, sig)

            state.last_price = price
            state.step += 1
            controller.tick()
        except Exception as exc:
            controller.fail(exc)

    try:
        console.print(f"[yellow]Starting strategy feed for {market} {cfg.interval} (dry-run).[/yellow]")
        if not every_update:
            console.print("[yellow]Processing closed candles only; first signal appears after the next candle starts.[/yellow]")
        info.subscribe({"type": "candle", "coin": market, "interval": cfg.interval}, on_msg)
        _wait_for_stream(info, controller, seconds)
    except Exception as e:
        console.print(f"[red]Strategy feed failed:[/red] {e}")
        raise typer.Exit(1)


def _wait_for_stream(info: Any, controller: StreamController, seconds: int | None) -> None:
    deadline = None if seconds is None else time.monotonic() + seconds
    try:
        while not controller.done.is_set():
            timeout = 0.5
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                timeout = min(timeout, remaining)
            controller.changed.wait(timeout)
            controller.changed.clear()
    except KeyboardInterrupt:
        console.print("[yellow]Stopping feed.[/yellow]")
    finally:
        info.disconnect_websocket()
    if controller.error is not None:
        raise controller.error


def _check_live_risk(
    signal: Signal,
    state: StrategyState,
    price: float,
    live_risk: dict,
    max_orders: int | None,
    max_notional: float | None,
    max_position: float | None,
    cooldown_seconds: float,
) -> None:
    if signal.action == SignalAction.SELL and state.position < signal.size:
        raise RuntimeError("sell signal exceeds local position; refusing to open short exposure")

    if max_position is not None and signal.action == SignalAction.BUY and state.position + signal.size > max_position:
        raise RuntimeError("signal would exceed --max-position")

    notional = _signal_notional(signal, price)
    if max_orders is not None and live_risk["orders"] >= max_orders:
        raise RuntimeError("--max-orders reached")
    if max_notional is not None and live_risk["notional"] + notional > max_notional:
        raise RuntimeError("--max-notional would be exceeded")
    if cooldown_seconds > 0 and time.monotonic() - live_risk["last_order_monotonic"] < cooldown_seconds:
        raise RuntimeError("--cooldown-seconds has not elapsed since the last order")


def _record_live_risk(signal: Signal, price: float, live_risk: dict) -> None:
    live_risk["orders"] += 1
    live_risk["notional"] += _signal_notional(signal, price)
    live_risk["last_order_monotonic"] = time.monotonic()


def _signal_notional(signal: Signal, price: float) -> float:
    return (signal.price or price) * signal.size


def _execute_signal(
    client: Any,
    signal: Signal,
    slippage: float,
    market_type: str,
    state: StrategyState,
    current_price: float,
) -> dict:
    is_buy = signal.action == SignalAction.BUY
    reduce_only = market_type == "perp" and signal.action == SignalAction.SELL
    if signal.action == SignalAction.SELL and state.position < signal.size:
        raise RuntimeError("sell signal exceeds local position; refusing to execute")

    if signal.order_type == "limit" and signal.price is not None:
        return client.exchange.order(
            signal.coin,
            is_buy,
            signal.size,
            signal.price,
            {"limit": {"tif": "Gtc"}},
            reduce_only=reduce_only,
        )

    if reduce_only:
        px = client.exchange._slippage_price(signal.coin, is_buy, slippage, current_price)
        return client.exchange.order(
            signal.coin,
            is_buy,
            signal.size,
            px,
            {"limit": {"tif": "Ioc"}},
            reduce_only=True,
        )

    return client.exchange.market_open(signal.coin, is_buy, signal.size, None, slippage)


def _apply_local_position(state: StrategyState, signal: Signal) -> None:
    if signal.action == SignalAction.BUY:
        state.position += signal.size
    elif signal.action == SignalAction.SELL:
        state.position = max(0.0, state.position - signal.size)


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _print_price_rows(rows: list[tuple[str, Any]]) -> None:
    table = Table(title=f"Live Mids ({_utc_now()})")
    table.add_column("Coin", style="cyan")
    table.add_column("Mid", justify="right", style="green")
    for coin, mid in rows:
        table.add_row(coin, str(mid))
    console.print(table)


def _print_trades(trades: list[dict]) -> None:
    if not trades:
        return
    table = Table(title="Trades")
    table.add_column("Time", style="cyan")
    table.add_column("Coin")
    table.add_column("Side")
    table.add_column("Size", justify="right")
    table.add_column("Price", justify="right", style="green")
    for trade in trades:
        table.add_row(
            format_time_ms(trade.get("time")),
            str(trade.get("coin", "")),
            format_side(trade.get("side"), plain=True),
            str(trade.get("sz", "")),
            str(trade.get("px", "")),
        )
    console.print(table)


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
