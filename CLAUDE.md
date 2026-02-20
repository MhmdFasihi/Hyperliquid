# CLAUDE.md — AI Development Context

## Project Overview

CLI tool for trading on Hyperliquid DEX (spot + perpetuals). Built with Typer for the CLI framework, Rich for output formatting, and the official `hyperliquid-python-sdk` for API access.

## Architecture

```
hyper_cli/
├── main.py      → Root Typer app. Registers spot + perp sub-apps. Has shared commands (status, cancel-all).
├── spot.py      → All spot trading commands (buy, sell, market-buy/sell, cancel, modify, orders, balances).
├── perp.py      → All perp trading commands (long, short, market-open/close, tp, sl, leverage, positions).
├── client.py    → HyperClient class. Lazy-initializes Exchange and Info from config. One instance per CLI invocation.
├── config.py    → Loads config.json (secret_key + account_address). Searches CWD then project root.
└── display.py   → All Rich output functions: tables for orders/positions/balances, formatted order responses.
```

## Key Patterns

- **API Agent Auth**: `secret_key` is the agent's private key, `account_address` is the main wallet. The agent signs trades on behalf of the main wallet.
- **Lazy Initialization**: `HyperClient.exchange` and `.info` are only created when first accessed.
- **Mainnet Only**: Hardcoded to `constants.MAINNET_API_URL`. No testnet toggle yet.
- **No WebSocket**: `skip_ws=True` — all commands are request/response.
- **Sub-apps**: `hyper spot ...` and `hyper perp ...` are separate Typer apps registered on the root app.

## SDK Reference

- `Exchange.order(coin, is_buy, sz, limit_px, order_type, reduce_only=False)` — place any order
- `Exchange.market_open(coin, is_buy, sz, px, slippage)` — market open
- `Exchange.market_close(coin, px, sz, slippage)` — market close
- `Exchange.cancel(coin, oid)` — cancel by OID
- `Exchange.bulk_cancel(cancel_requests)` — cancel multiple
- `Exchange.modify_order(oid, coin, is_buy, sz, px, order_type)` — modify
- `Exchange.update_leverage(leverage, coin, is_cross)` — set leverage
- `Info.spot_user_state(address)` — spot balances
- `Info.user_state(address)` — perp positions + margin
- `Info.open_orders(address)` — all open orders
- `Info.query_order_by_oid(address, oid)` — order status

## Adding New Commands

1. Add the command function in the appropriate file (`spot.py`, `perp.py`, or `main.py`)
2. Use `@app.command()` decorator
3. Use `Annotated[type, typer.Argument/Option(...)]` for parameters
4. Call `get_client()` to get the SDK client
5. Use display functions from `display.py` for output
6. Wrap SDK calls in try/except, print errors with `console.print("[red]...[/red]")`

## Dependencies

- `hyperliquid-python-sdk` — Official Hyperliquid API SDK
- `typer` — CLI framework
- `rich` — Terminal formatting
- `eth-account` — Wallet/signing (pulled in by SDK)

## Environment

- Python 3.10 (conda env: `hyper`)
- Install: `pip install -e .`
- Entry point: `hyper` command (defined in pyproject.toml)

## Testing

No test suite yet. Verify manually:
- `hyper --help`, `hyper spot --help`, `hyper perp --help`
- `hyper spot balances` — tests config loading + API connection
- `hyper perp positions` — tests perp API
