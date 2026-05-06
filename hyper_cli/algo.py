"""Algotrading framework commands."""

import json
import math
from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated

from hyper_cli.backtest import run_backtest
from hyper_cli.client import get_info
from hyper_cli.display import console, print_backtest_result, print_signal, print_strategy_catalog
from hyper_cli.market import INTERVAL_MS, find_mid, normalize_coin, now_ms
from hyper_cli.strategies import (
    STRATEGIES,
    MarketSnapshot,
    StrategyConfigError,
    StrategyState,
    build_strategy,
    load_strategy_config,
    strategy_template,
)
from hyper_cli.validation import require_non_negative, require_positive

app = typer.Typer(help="Algotrading framework commands", no_args_is_help=True)


@app.command("strategies")
def list_strategies() -> None:
    """List built-in strategy types."""
    print_strategy_catalog(STRATEGIES)


@app.command()
def template(
    strategy: Annotated[str, typer.Argument(help="Strategy name: grid, twap, or dca")],
    output_format: Annotated[str, typer.Option("--format", "-f", help="json or yaml")] = "json",
) -> None:
    """Print a starter strategy config."""
    try:
        data = strategy_template(strategy)
    except StrategyConfigError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    fmt = output_format.lower()
    if fmt == "json":
        console.print(json.dumps(data, indent=2))
        return
    if fmt in ("yaml", "yml"):
        console.print(_dump_simple_yaml(data))
        return

    console.print("[red]--format must be json or yaml[/red]")
    raise typer.Exit(1)


@app.command()
def signal(
    config: Annotated[Path, typer.Argument(help="Strategy config file (.json, .yaml, .yml)")],
    price: Annotated[Optional[float], typer.Option("--price", "-p", help="Use this price instead of fetching mids")] = None,
    previous_price: Annotated[
        Optional[float],
        typer.Option("--previous-price", help="Previous price for crossing strategies such as grid"),
    ] = None,
    step: Annotated[int, typer.Option("--step", min=0, help="Strategy step index for TWAP/DCA")] = 0,
    position: Annotated[float, typer.Option("--position", min=0.0, help="Current base-asset position")] = 0.0,
) -> None:
    """Generate the next signal from a strategy config."""
    require_non_negative("position", position)
    if price is not None:
        require_positive("price", price)
    if previous_price is not None:
        require_positive("previous_price", previous_price)
    try:
        cfg = load_strategy_config(config)
        strategy = build_strategy(cfg)
        signal_price = price if price is not None else _fetch_current_price(cfg.coin)
        state = StrategyState(position=position, last_price=previous_price, step=step)
        snapshot = MarketSnapshot(cfg.coin, signal_price)
        print_signal(strategy.generate_signal(snapshot, state))
    except StrategyConfigError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to generate signal:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def backtest(
    config: Annotated[Path, typer.Argument(help="Strategy config file (.json, .yaml, .yml)")],
    limit: Annotated[Optional[int], typer.Option("--limit", "-n", min=1, help="Number of candles to fetch")] = None,
    start_ms: Annotated[Optional[int], typer.Option("--start-ms", help="Start time in Unix milliseconds")] = None,
    end_ms: Annotated[Optional[int], typer.Option("--end-ms", help="End time in Unix milliseconds")] = None,
    trades: Annotated[int, typer.Option("--trades", min=0, help="Number of recent trades to print")] = 10,
) -> None:
    """Backtest a strategy over historical candle closes."""
    try:
        cfg = load_strategy_config(config)
        interval_ms = INTERVAL_MS.get(cfg.interval)
        if interval_ms is None:
            allowed = ", ".join(INTERVAL_MS)
            console.print(f"[red]Invalid interval '{cfg.interval}'. Use one of: {allowed}[/red]")
            raise typer.Exit(1)

        candle_limit = limit or _positive_config_int(cfg.backtest, "limit", 200)
        end_time = end_ms or now_ms()
        start_time = start_ms or (end_time - interval_ms * candle_limit)
        info = get_info()
        market = normalize_coin(info, cfg.coin)
        candles = info.candles_snapshot(market, cfg.interval, start_time, end_time)
        if limit is not None:
            candles = candles[-limit:]

        strategy = build_strategy(cfg)
        starting_cash = _non_negative_config_float(cfg.backtest, "starting_cash", 10000)
        starting_position = _non_negative_config_float(cfg.backtest, "starting_position", 0)
        fee_rate = _non_negative_config_float(cfg.backtest, "fee_rate", 0)
        slippage_bps = _non_negative_config_float(cfg.backtest, "slippage_bps", 0)
        if slippage_bps > 10_000:
            raise StrategyConfigError("backtest.slippage_bps must be at most 10000.")
        result = run_backtest(strategy, candles, starting_cash, starting_position, fee_rate, slippage_bps)
        print_backtest_result(result, trades)
    except typer.Exit:
        raise
    except StrategyConfigError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Backtest failed:[/red] {e}")
        raise typer.Exit(1)


def _fetch_current_price(coin: str) -> float:
    info = get_info()
    mids = info.all_mids()
    match = find_mid(mids, info.name_to_coin, coin)
    if match is None:
        raise StrategyConfigError(f"No mid price found for {coin}. Pass --price to avoid a live lookup.")
    try:
        price = float(match[1])
    except (TypeError, ValueError) as exc:
        raise StrategyConfigError(f"Mid price for {coin} is malformed: {match[1]}") from exc
    if not math.isfinite(price) or price <= 0:
        raise StrategyConfigError(f"Mid price for {coin} must be a finite number greater than 0.")
    return price


def _non_negative_config_float(backtest: dict, key: str, default: float) -> float:
    raw = backtest.get(key, default)
    if isinstance(raw, bool):
        raise StrategyConfigError(f"backtest.{key} must be a number.")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise StrategyConfigError(f"backtest.{key} must be a number.") from exc
    if not math.isfinite(value) or value < 0:
        raise StrategyConfigError(f"backtest.{key} must be a finite number >= 0.")
    return value


def _positive_config_int(backtest: dict, key: str, default: int) -> int:
    raw = backtest.get(key, default)
    if isinstance(raw, bool):
        raise StrategyConfigError(f"backtest.{key} must be an integer.")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise StrategyConfigError(f"backtest.{key} must be an integer.") from exc
    if value <= 0:
        raise StrategyConfigError(f"backtest.{key} must be greater than 0.")
    return value


def _dump_simple_yaml(data: dict, indent: int = 0) -> str:
    lines: list[str] = []
    prefix = " " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_dump_simple_yaml(value, indent + 2))
        else:
            lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")
    return "\n".join(lines)


def _yaml_scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if any(char in text for char in (":", "#", "{", "}", "[", "]", ",")) or text == "":
        return json.dumps(text)
    return text
