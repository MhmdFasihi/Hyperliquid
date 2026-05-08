"""Simple candle-close backtesting engine for built-in strategies."""

from dataclasses import dataclass, field
import math
from typing import Any

from hyper_cli.strategies import BaseStrategy, MarketSnapshot, Signal, SignalAction, StrategyState


@dataclass(frozen=True)
class Trade:
    time_ms: int | None
    action: SignalAction
    price: float
    size: float
    fee: float
    cash: float
    position: float
    reason: str


@dataclass(frozen=True)
class BacktestResult:
    coin: str
    interval: str
    starting_cash: float
    starting_position: float
    initial_price: float
    final_price: float
    final_cash: float
    final_position: float
    final_equity: float
    total_fees: float
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[int | None, float]] = field(default_factory=list)
    skipped_signals: int = 0

    @property
    def starting_equity(self) -> float:
        return self.starting_cash + self.starting_position * self.initial_price

    @property
    def pnl(self) -> float:
        return self.final_equity - self.starting_equity

    @property
    def return_pct(self) -> float:
        if self.starting_equity == 0:
            return 0.0
        return self.pnl / self.starting_equity * 100

    @property
    def max_drawdown_pct(self) -> float:
        peak = None
        max_drawdown = 0.0
        for _, equity in self.equity_curve:
            peak = equity if peak is None else max(peak, equity)
            if peak > 0:
                max_drawdown = max(max_drawdown, (peak - equity) / peak * 100)
        return max_drawdown


def run_backtest(
    strategy: BaseStrategy,
    candles: list[dict[str, Any]],
    starting_cash: float = 10000.0,
    starting_position: float = 0.0,
    fee_rate: float = 0.0,
    slippage_bps: float = 0.0,
) -> BacktestResult:
    if not candles:
        raise ValueError("Backtest requires at least one candle.")

    starting_cash = _non_negative_float("starting_cash", starting_cash)
    starting_position = _non_negative_float("starting_position", starting_position)
    fee_rate = _non_negative_float("fee_rate", fee_rate)
    slippage_bps = _non_negative_float("slippage_bps", slippage_bps)
    if slippage_bps > 10_000:
        raise ValueError("slippage_bps must be at most 10000.")

    ordered = sorted(candles, key=lambda candle: candle.get("t", 0))
    cash = starting_cash
    position = starting_position
    total_fees = 0.0
    skipped_signals = 0
    pending: list[Signal] = []
    trades: list[Trade] = []
    equity_curve: list[tuple[int | None, float]] = []
    state = StrategyState(cash=cash, position=position)

    initial_price = _positive_price("initial close", ordered[0]["c"])
    final_price = initial_price

    for candle in ordered:
        price = _positive_price("close", candle["c"])
        open_price = _positive_price("open", candle.get("o", price))
        final_price = price
        time_ms = candle.get("t")

        still_pending: list[Signal] = []
        for pending_signal in pending:
            trade, keep_pending = _try_execute_pending(
                pending_signal,
                candle,
                cash,
                position,
                open_price,
                time_ms,
                fee_rate,
                slippage_bps,
            )
            if trade is not None:
                cash = trade.cash
                position = trade.position
                total_fees += trade.fee
                trades.append(trade)
            elif keep_pending:
                still_pending.append(pending_signal)
            else:
                skipped_signals += 1
        pending = still_pending

        state.cash = cash
        state.position = position
        snapshot = MarketSnapshot(strategy.coin, price, time_ms, candle)
        signal = strategy.generate_signal(snapshot, state)
        if signal.action != SignalAction.HOLD:
            if _valid_pending_signal(signal):
                pending.append(signal)
            else:
                skipped_signals += 1

        equity_curve.append((time_ms, cash + position * price))
        state.last_price = price
        state.step += 1

    skipped_signals += len(pending)
    final_equity = cash + position * final_price
    return BacktestResult(
        coin=strategy.coin,
        interval=strategy.interval,
        starting_cash=starting_cash,
        starting_position=starting_position,
        initial_price=initial_price,
        final_price=final_price,
        final_cash=cash,
        final_position=position,
        final_equity=final_equity,
        total_fees=total_fees,
        trades=trades,
        equity_curve=equity_curve,
        skipped_signals=skipped_signals,
    )


def _try_execute_pending(
    signal: Signal,
    candle: dict[str, Any],
    cash: float,
    position: float,
    open_price: float,
    time_ms: int | None,
    fee_rate: float,
    slippage_bps: float,
) -> tuple[Trade | None, bool]:
    if signal.action == SignalAction.HOLD or not _valid_pending_signal(signal):
        return None, False

    execution_price = _execution_price(signal, candle, open_price, slippage_bps)
    if execution_price is None:
        return None, signal.order_type == "limit"

    if signal.action == SignalAction.BUY:
        notional = execution_price * signal.size
        fee = notional * fee_rate
        if notional + fee > cash:
            return None, False
        return (
            Trade(
                time_ms,
                signal.action,
                execution_price,
                signal.size,
                fee,
                cash - notional - fee,
                position + signal.size,
                signal.reason,
            ),
            False,
        )

    size = min(signal.size, position)
    if size <= 0:
        return None, False
    notional = execution_price * size
    fee = notional * fee_rate
    return (
        Trade(
            time_ms,
            signal.action,
            execution_price,
            size,
            fee,
            cash + notional - fee,
            position - size,
            signal.reason,
        ),
        False,
    )


def _execution_price(
    signal: Signal,
    candle: dict[str, Any],
    open_price: float,
    slippage_bps: float,
) -> float | None:
    if signal.order_type == "limit" and signal.price is not None:
        high = _positive_price("high", candle.get("h", open_price))
        low = _positive_price("low", candle.get("l", open_price))
        if signal.action == SignalAction.BUY and low <= signal.price:
            return signal.price
        if signal.action == SignalAction.SELL and high >= signal.price:
            return signal.price
        return None

    slippage = slippage_bps / 10_000
    if signal.action == SignalAction.BUY:
        return open_price * (1 + slippage)
    if signal.action == SignalAction.SELL:
        return open_price * (1 - slippage)
    return None


def _valid_pending_signal(signal: Signal) -> bool:
    try:
        size = float(signal.size)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(size) or size <= 0:
        return False
    if signal.price is not None:
        try:
            price = float(signal.price)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(price) or price <= 0:
            return False
    return True


def _non_negative_float(name: str, raw: Any) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite number >= 0.")
    return value


def _positive_price(name: str, raw: Any) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite number > 0.")
    return value
