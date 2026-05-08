"""Strategy definitions and config loading for the algo framework."""

import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class StrategyConfigError(ValueError):
    """Raised when a strategy config is invalid."""


class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass(frozen=True)
class Signal:
    action: SignalAction
    coin: str
    size: float = 0.0
    price: float | None = None
    order_type: str = "market"
    reason: str = ""


@dataclass(frozen=True)
class MarketSnapshot:
    coin: str
    price: float
    timestamp_ms: int | None = None
    candle: dict[str, Any] | None = None


@dataclass
class StrategyState:
    cash: float = 0.0
    position: float = 0.0
    last_price: float | None = None
    step: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    coin: str
    interval: str = "1h"
    market_type: str = "perp"
    params: dict[str, Any] = field(default_factory=dict)
    backtest: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "StrategyConfig":
        if not isinstance(raw, dict):
            raise StrategyConfigError("Strategy config must be a JSON/YAML object.")

        strategy_name = raw.get("strategy") or raw.get("name")
        raw_params = raw.get("params") or {}
        if not isinstance(raw_params, dict):
            raise StrategyConfigError("params must be an object.")
        params = dict(raw_params)

        if isinstance(strategy_name, dict):
            strategy_block = strategy_name
            strategy_name = strategy_block.get("name")
            block_params = strategy_block.get("params", {}) or {}
            if not isinstance(block_params, dict):
                raise StrategyConfigError("strategy.params must be an object.")
            params = {**block_params, **params}

        coin = raw.get("coin")
        if not strategy_name:
            raise StrategyConfigError("Missing required field: strategy")
        if not coin:
            raise StrategyConfigError("Missing required field: coin")

        market_type = str(raw.get("market_type", "perp")).lower()
        if market_type not in ("perp", "spot"):
            raise StrategyConfigError("market_type must be 'perp' or 'spot'.")
        backtest = raw.get("backtest") or {}
        if not isinstance(backtest, dict):
            raise StrategyConfigError("backtest must be an object.")

        return cls(
            name=str(strategy_name).lower(),
            coin=str(coin),
            interval=str(raw.get("interval", "1h")),
            market_type=market_type,
            params=params,
            backtest=dict(backtest),
        )


class BaseStrategy(ABC):
    """Base class for stateless signal generation over sequential market snapshots."""

    name = "base"
    description = "Base strategy"
    parameter_help: dict[str, str] = {}

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.coin = config.coin
        self.interval = config.interval
        self.params = config.params
        self.validate()

    @abstractmethod
    def validate(self) -> None:
        """Validate strategy-specific params."""

    @abstractmethod
    def generate_signal(self, snapshot: MarketSnapshot, state: StrategyState) -> Signal:
        """Generate one signal from the latest snapshot and current strategy state."""

    def hold(self, reason: str) -> Signal:
        return Signal(SignalAction.HOLD, self.coin, reason=reason)


class GridStrategy(BaseStrategy):
    name = "grid"
    description = "Buy when price crosses down a grid level; sell inventory when it crosses up."
    parameter_help = {
        "lower_price": "Lower grid boundary",
        "upper_price": "Upper grid boundary",
        "levels": "Number of grid levels, including boundaries",
        "order_size": "Base-asset size for each grid order",
    }

    def validate(self) -> None:
        self.lower_price = _positive_float(self.params, "lower_price")
        self.upper_price = _positive_float(self.params, "upper_price")
        self.level_count = _positive_int(self.params, "levels")
        self.order_size = _positive_float(self.params, "order_size")

        if self.upper_price <= self.lower_price:
            raise StrategyConfigError("grid upper_price must be greater than lower_price.")
        if self.level_count < 2:
            raise StrategyConfigError("grid levels must be at least 2.")

        step = (self.upper_price - self.lower_price) / (self.level_count - 1)
        self.levels = [self.lower_price + step * i for i in range(self.level_count)]

    def generate_signal(self, snapshot: MarketSnapshot, state: StrategyState) -> Signal:
        price = snapshot.price
        if price < self.lower_price or price > self.upper_price:
            return self.hold("price is outside the configured grid range")

        if state.last_price is None:
            nearest = min(self.levels, key=lambda level: abs(level - price))
            return self.hold(f"waiting for first grid crossing; nearest level is {nearest:.8g}")

        crossed_down = [level for level in self.levels if state.last_price > level >= price]
        if crossed_down:
            level = max(crossed_down)
            return Signal(
                SignalAction.BUY,
                self.coin,
                size=self.order_size,
                price=level,
                order_type="limit",
                reason=f"price crossed down through grid level {level:.8g}",
            )

        crossed_up = [level for level in self.levels if state.last_price < level <= price]
        if crossed_up:
            level = min(crossed_up)
            if state.position < self.order_size:
                return self.hold(f"price crossed up through {level:.8g}, but no inventory is available")
            return Signal(
                SignalAction.SELL,
                self.coin,
                size=self.order_size,
                price=level,
                order_type="limit",
                reason=f"price crossed up through grid level {level:.8g}",
            )

        return self.hold("no grid level crossed")


class TwapStrategy(BaseStrategy):
    name = "twap"
    description = "Split one target order into equal slices across sequential candles."
    parameter_help = {
        "side": "buy or sell",
        "total_size": "Total base-asset size to execute",
        "slices": "Number of equal order slices",
    }

    def validate(self) -> None:
        self.side = _side(self.params.get("side", "buy"))
        self.total_size = _positive_float(self.params, "total_size")
        self.slices = _positive_int(self.params, "slices")
        self.slice_size = self.total_size / self.slices

    def generate_signal(self, snapshot: MarketSnapshot, state: StrategyState) -> Signal:
        if state.step >= self.slices:
            return self.hold("all TWAP slices have been emitted")

        return Signal(
            SignalAction(self.side),
            self.coin,
            size=self.slice_size,
            price=snapshot.price,
            order_type="market",
            reason=f"TWAP slice {state.step + 1} of {self.slices}",
        )


class DcaStrategy(BaseStrategy):
    name = "dca"
    description = "Emit a fixed-size order every N candles until max_orders is reached."
    parameter_help = {
        "side": "buy or sell",
        "size": "Base-asset size per order",
        "interval_candles": "Candles between orders",
        "max_orders": "Optional maximum order count",
    }

    def validate(self) -> None:
        self.side = _side(self.params.get("side", "buy"))
        self.size = _positive_float(self.params, "size")
        self.interval_candles = _positive_int(self.params, "interval_candles", default=1)
        max_orders = self.params.get("max_orders")
        self.max_orders = None if max_orders in (None, "") else _positive_int(self.params, "max_orders")

    def generate_signal(self, snapshot: MarketSnapshot, state: StrategyState) -> Signal:
        if state.step % self.interval_candles != 0:
            return self.hold("waiting for the next DCA interval")

        order_index = state.step // self.interval_candles
        if self.max_orders is not None and order_index >= self.max_orders:
            return self.hold("maximum DCA order count reached")

        return Signal(
            SignalAction(self.side),
            self.coin,
            size=self.size,
            price=snapshot.price,
            order_type="market",
            reason=f"DCA order {order_index + 1}",
        )


STRATEGIES: dict[str, type[BaseStrategy]] = {
    GridStrategy.name: GridStrategy,
    TwapStrategy.name: TwapStrategy,
    DcaStrategy.name: DcaStrategy,
}


def build_strategy(config: StrategyConfig) -> BaseStrategy:
    cls = STRATEGIES.get(config.name)
    if cls is None:
        names = ", ".join(sorted(STRATEGIES))
        raise StrategyConfigError(f"Unknown strategy '{config.name}'. Use one of: {names}")
    return cls(config)


def load_strategy_config(path: Path) -> StrategyConfig:
    raw = _load_config_file(path)
    return StrategyConfig.from_dict(raw)


def strategy_template(name: str) -> dict[str, Any]:
    templates = {
        "grid": {
            "strategy": "grid",
            "coin": "ETH",
            "market_type": "perp",
            "interval": "1h",
            "params": {
                "lower_price": 2200,
                "upper_price": 2600,
                "levels": 5,
                "order_size": 0.02,
            },
            "backtest": {
                "starting_cash": 10000,
                "fee_rate": 0.00035,
                "slippage_bps": 1,
                "limit": 200,
            },
        },
        "twap": {
            "strategy": "twap",
            "coin": "ETH",
            "market_type": "perp",
            "interval": "1h",
            "params": {
                "side": "buy",
                "total_size": 1.0,
                "slices": 10,
            },
            "backtest": {
                "starting_cash": 10000,
                "fee_rate": 0.00035,
                "slippage_bps": 1,
                "limit": 50,
            },
        },
        "dca": {
            "strategy": "dca",
            "coin": "ETH",
            "market_type": "perp",
            "interval": "1h",
            "params": {
                "side": "buy",
                "size": 0.05,
                "interval_candles": 24,
                "max_orders": 10,
            },
            "backtest": {
                "starting_cash": 10000,
                "fee_rate": 0.00035,
                "slippage_bps": 1,
                "limit": 300,
            },
        },
    }
    try:
        return templates[name.lower()]
    except KeyError as exc:
        names = ", ".join(sorted(templates))
        raise StrategyConfigError(f"Unknown template '{name}'. Use one of: {names}") from exc


def _load_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise StrategyConfigError(f"Config file not found: {path}")

    suffix = path.suffix.lower()
    text = path.read_text()
    if suffix == ".json":
        return json.loads(text)
    if suffix in (".yaml", ".yml"):
        return _load_yaml(text)

    raise StrategyConfigError("Strategy config must be a .json, .yaml, or .yml file.")


def _load_yaml(text: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        return data or {}
    except ModuleNotFoundError:
        return _load_simple_yaml(text)


def _load_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the simple nested key/value YAML shape emitted by `hyper algo template`."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = _strip_inline_comment(raw_line.strip())
        if not line:
            continue
        if ":" not in line:
            raise StrategyConfigError("YAML fallback only supports key/value mappings.")

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()

        current = stack[-1][1]
        if not value:
            nested: dict[str, Any] = {}
            current[key] = nested
            stack.append((indent, nested))
        else:
            current[key] = _parse_scalar(value)

    return root


def _parse_scalar(value: str) -> Any:
    if value in ("null", "Null", "NULL", "~"):
        return None
    if value in ("true", "True", "TRUE"):
        return True
    if value in ("false", "False", "FALSE"):
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _strip_inline_comment(line: str) -> str:
    quote: str | None = None
    for idx, char in enumerate(line):
        if char in ("'", '"'):
            quote = None if quote == char else char
        elif char == "#" and quote is None:
            return line[:idx].rstrip()
    return line


def _positive_float(params: dict[str, Any], key: str, default: float | None = None) -> float:
    raw = params.get(key, default)
    if raw is None:
        raise StrategyConfigError(f"Missing required param: {key}")
    if isinstance(raw, bool):
        raise StrategyConfigError(f"Param {key} must be a number.")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise StrategyConfigError(f"Param {key} must be a number.") from exc
    if not math.isfinite(value) or value <= 0:
        raise StrategyConfigError(f"Param {key} must be a finite number greater than 0.")
    return value


def _positive_int(params: dict[str, Any], key: str, default: int | None = None) -> int:
    raw = params.get(key, default)
    if raw is None:
        raise StrategyConfigError(f"Missing required param: {key}")
    if isinstance(raw, bool):
        raise StrategyConfigError(f"Param {key} must be an integer.")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise StrategyConfigError(f"Param {key} must be an integer.") from exc
    if value <= 0:
        raise StrategyConfigError(f"Param {key} must be greater than 0.")
    return value


def _side(raw: Any) -> str:
    value = str(raw).lower()
    if value in ("buy", "b", "long"):
        return SignalAction.BUY.value
    if value in ("sell", "s", "short"):
        return SignalAction.SELL.value
    raise StrategyConfigError("Param side must be buy or sell.")
