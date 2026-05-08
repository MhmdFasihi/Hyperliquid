# CLAUDE.md — AI Development Context

## Project Overview

CLI tool for trading on Hyperliquid DEX (spot + perpetuals), account management, market data, strategy backtesting, and real-time feeds. Built with Typer for the CLI framework, Rich for output formatting, and the official `hyperliquid-python-sdk` for API access.

## Architecture

```
hyper_cli/
├── main.py      → Root Typer app. Registers spot/perp/account/algo/feed sub-apps. Has shared and market data commands.
├── spot.py      → All spot trading commands (buy, sell, market-buy/sell, cancel, modify, orders, balances).
├── perp.py      → All perp trading commands (long, short, market-open/close, tp, sl, leverage, positions).
├── account.py   → Account commands (spot/perp transfers, withdrawals, history, sub-accounts).
├── algo.py      → Algotrading commands (templates, signals, backtests).
├── feed.py      → WebSocket feeds (prices, book, trades, account events, live strategy triggers).
├── strategies.py → Strategy base class, config loading, and built-in grid/TWAP/DCA strategies.
├── backtest.py  → Candle-close backtesting engine.
├── market.py    → Shared market data helpers (intervals, coin normalization, mids).
├── client.py    → HyperClient class. Lazy-initializes Exchange and Info from config. One instance per CLI invocation.
├── config.py    → Loads config.json (agent_secret_key + account_address + optional main_wallet_secret_key). Searches CWD then project root.
├── display.py   → Rich output functions: tables for orders/positions/balances, formatted action responses.
├── responses.py → Central SDK action-response parser for top-level/per-status outcomes.
└── validation.py → Shared side, numeric, address, Decimal USDC, and confirmation helpers.
```

## Key Patterns

- **API Agent Auth**: `agent_secret_key` is the API agent's private key, `account_address` is the main wallet. Legacy `secret_key` is still accepted as the agent key.
- **Main Wallet Actions**: withdrawals, spot/perp transfers, and sub-account mutation use `main_wallet_secret_key` through `HyperClient.main_wallet_exchange`.
- **Lazy Initialization**: `HyperClient.exchange` and `.info` are only created when first accessed.
- **Public Info Client**: `get_info()` creates a read-only `Info` client for market data commands that do not need `config.json`; market/feed/perp commands accept `--dex` where the SDK supports builder-deployed perp DEXs.
- **Per-DEX Clients**: Use `HyperClient.info_for_dex(dex)` and `HyperClient.exchange_for_dex(dex)` for non-default perp DEX commands. Normalize builder symbols with `market.normalize_coin(info, coin, dex)`.
- **Mainnet Only**: Hardcoded to `constants.MAINNET_API_URL`. No testnet toggle yet.
- **WebSocket Feeds**: `get_ws_info()` loads market metadata first, then starts a WebSocket manager for `hyper feed ...`; this avoids orphaned WebSocket threads when metadata/network initialization fails.
- **Sub-apps**: `hyper spot ...` and `hyper perp ...` are separate Typer apps registered on the root app.
- **Market Data**: `hyper price`, `hyper prices`, `hyper book`, `hyper candles`, and `hyper funding` are top-level read-only commands in `main.py`.
- **Algo Framework**: `hyper algo ...` is dry-run/backtesting only. `hyper feed strategy --execute` is disabled in this release; run without `--execute` for dry-run live candle signals.
- **Strategy Configs**: JSON is built-in. YAML uses PyYAML when installed and a simple fallback parser for the emitted template shape.
- **Real-Time Feeds**: `hyper feed ...` uses WebSocket subscriptions. DEX mid-price feeds include the normalized `dex` field in `allMids` subscriptions. Trade rendering must tolerate unknown side codes and malformed timestamps.
- **Safety Helpers**: side parsing, finite numeric checks, address validation, Decimal USDC parsing, and confirmation prompts are centralized in `validation.py`.
- **SDK Response Handling**: live action paths must use `print_and_require_success()` or `parse_action_response()` and exit non-zero on top-level failures, per-status errors, or unknown statuses.
- **Confirmation Rules**: market orders, modify commands, fund-moving commands, and bulk-cancel commands prompt unless `--yes` is passed. Spot/perp market orders and modify commands also support `--dry-run`.
- **Fund Amounts**: account amounts are string arguments parsed as Decimal USDC, reject scientific notation, and allow at most 6 decimal places. Sub-account transfers convert to exact micro-USDC integers.
- **Perp Modify**: requires explicit `--reduce-only` or `--not-reduce-only` and passes that boolean to the SDK.

## SDK Reference

- `Exchange.order(coin, is_buy, sz, limit_px, order_type, reduce_only=False)` — place any order
- `Exchange.market_open(coin, is_buy, sz, px, slippage)` — market open
- `Exchange.market_close(coin, sz=None, px=None, slippage=...)` — market close
- `Exchange.cancel(coin, oid)` — cancel by OID
- `Exchange.bulk_cancel(cancel_requests)` — cancel multiple
- `Exchange.modify_order(oid, coin, is_buy, sz, px, order_type, reduce_only=...)` — modify
- `Exchange.update_leverage(leverage, coin, is_cross)` — set leverage
- `Info.spot_user_state(address)` — spot balances
- `Info.user_state(address, dex="")` — perp positions + margin
- `Info.open_orders(address, dex="")` — all open orders
- `Info.query_order_by_oid(address, oid)` — order status
- `Info.all_mids(dex="")` — all current mid prices
- `Info.l2_snapshot(coin)` — L2 order book snapshot
- `Info.candles_snapshot(coin, interval, startTime, endTime)` — OHLCV candles
- `Info.funding_history(coin, startTime, endTime)` — historical funding rates
- `Info.meta_and_asset_ctxs()` — current perp asset contexts, including funding
- `Info.subscribe(subscription, callback)` — WebSocket feeds (`allMids`, `l2Book`, `trades`, `userEvents`, `orderUpdates`, `userFills`, `candle`)

## Adding New Commands

1. Add the command function in the appropriate file (`spot.py`, `perp.py`, or `main.py`)
2. Use `@app.command()` decorator
3. Use `Annotated[type, typer.Argument/Option(...)]` for parameters
4. Call `get_client()` to get the SDK client
5. Use display functions from `display.py` for output
6. Parse SDK action responses with `print_and_require_success()` or `parse_action_response()`; failed SDK responses must exit non-zero.
7. Add finite-number validation for every numeric CLI/config input that can reach SDK or strategy logic.

## Dependencies

- `hyperliquid-python-sdk` — Official Hyperliquid API SDK
- `typer` — CLI framework
- `rich` — Terminal formatting
- `shellingham` — Shell completion support used by Typer
- `PyYAML` — Full YAML strategy config parsing
- `eth-account` — Wallet/signing (pulled in by SDK)

## Environment

- Python 3.10 (conda env: `hyper`)
- Install: `pip install -e .`
- Entry point: `hyper` command (defined in pyproject.toml)

## Testing

Run the automated safety tests and command smoke checks:

- `python -m compileall hyper_cli tests`
- `python -m unittest discover -s tests`
- `hyper --help`, `hyper spot --help`, `hyper perp --help`
- `hyper price ETH`, `hyper book ETH`, `hyper candles ETH 1h`
- `hyper algo strategies`, `hyper algo template grid > grid_strategy.json`
- `hyper algo signal grid_strategy.json --price 2300 --previous-price 2400`
- `hyper algo backtest grid_strategy.json --limit 10`
- `hyper feed prices --coins ETH --updates 1`, `hyper feed book ETH --depth 1 --updates 1`
- `hyper feed strategy grid_strategy.json --updates 1` — dry-run closed-candle live signal
- `hyper feed strategy grid_strategy.json --execute` — should fail immediately because live execution is disabled
- `hyper spot balances` — tests config loading + API connection
- `hyper perp positions` — tests perp API
