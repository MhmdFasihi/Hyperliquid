# Hyperliquid Trading CLI

A command-line interface for trading, account management, market data, strategy backtesting, and real-time feeds on [Hyperliquid DEX](https://hyperliquid.xyz) — spot and perpetual markets.

Built on top of the official [hyperliquid-python-sdk](https://github.com/hyperliquid-dex/hyperliquid-python-sdk).

## Features

**Spot Trading**
- Limit buy/sell orders with GTC, IOC, ALO time-in-force
- Market buy/sell orders with configurable slippage, confirmation prompts, and dry-run previews
- Cancel, cancel-all, and modify orders; modify prompts before signing
- View balances and open orders

**Perpetual Trading**
- Long/short limit orders
- Market open/close positions (full or partial); market-open prompts before signing
- Take-profit and stop-loss orders
- Leverage management (cross and isolated margin)
- Builder-deployed perp DEX support via `--dex` where the SDK supports it
- View positions, margin summary, and open orders

**Account Management**
- Transfer USDC between spot and perp accounts
- Withdraw USDC
- View transaction history
- Manage sub-accounts

**Market Data**
- Current mid prices for one market or all markets
- L2 order book snapshots
- OHLCV candle snapshots
- Current and historical funding rates

**Algotrading Framework**
- Strategy base class and signal generation model
- Built-in grid, TWAP, and DCA strategies
- Candle-close backtesting without same-candle lookahead, with OHLC limit-touch checks and configurable slippage
- Strategy configs via JSON or YAML

**Real-Time Feeds**
- WebSocket mid-price feeds
- Real-time order book and trade streams
- Account event notifications
- Strategy signals from closed live candle triggers; live order execution is currently disabled

**General**
- Check any order status by OID
- Cancel all open orders across spot and perp in one command
- Rich formatted output with colored tables

## Quick Start

### 1. Create conda environment

```bash
conda create -n hyper python=3.10 -y
conda activate hyper
```

### 2. Install

```bash
cd /path/to/hyperliquid
pip install -e .
```

### 3. Configure credentials

Market data commands work without credentials. Trading and account commands require `config.json`.

```bash
cp config.json.example config.json
```

Edit `config.json` with your API agent credentials:

```json
{
    "agent_secret_key": "0xYOUR_AGENT_PRIVATE_KEY",
    "account_address": "0xYOUR_MAIN_WALLET_ADDRESS",
    "main_wallet_secret_key": "",
    "network": "mainnet"
}
```

- `agent_secret_key` — Your API agent's private key (generated at [app.hyperliquid.xyz/API](https://app.hyperliquid.xyz/API))
- `account_address` — Your main wallet's public address
- `main_wallet_secret_key` — Optional. Required only for user-signed account actions such as withdrawals, spot/perp transfers, and sub-account mutation.
- `network` — `mainnet` or `testnet`. Authenticated commands use this value from `config.json`; public market/feed commands can also use `HYPERLIQUID_NETWORK=testnet`.

Older configs using `secret_key` are still accepted as the agent key, but new configs should use `agent_secret_key`.

### 4. Verify

```bash
hyper spot balances
hyper perp positions
```

## Usage Examples

```bash
# Spot trading
hyper spot buy PURR/USDC 24 0.5 --tif gtc
hyper spot sell PURR/USDC 24 0.51
hyper spot market-buy PURR/USDC 100 --dry-run
hyper spot market-buy PURR/USDC 100 --yes
hyper spot modify 123456 PURR/USDC buy 30 0.48 --dry-run
hyper spot balances
hyper spot orders

# Perp trading
hyper perp long ETH 0.2 1100
hyper perp short BTC 0.01 100000 --tif alo
hyper perp market-open ETH buy 0.1 --slippage 0.01 --yes
hyper perp market-close ETH
hyper perp tp ETH sell 0.2 3500 --trigger 3400
hyper perp sl ETH sell 0.2 2500 --trigger 2600
hyper perp leverage ETH 10
hyper perp leverage ETH 5 --isolated
hyper perp modify 123456 ETH buy 0.1 2400 --not-reduce-only --dry-run
hyper perp positions
hyper perp orders GOLD --dex xyz

# Account management
hyper account spot-to-perp 100 --yes
hyper account perp-to-spot 50 --yes
hyper account withdraw 100 --to 0xabc... --yes
hyper account history --days 7
hyper account sub-accounts

# Market data
hyper price ETH
hyper price GOLD --dex xyz
hyper prices
hyper book GOLD --dex xyz --depth 10
hyper book BRENTOIL --dex xyz --depth 10
hyper book WTIOIL --dex xyz --depth 10    # resolves to BRENTOIL when WTIOIL is unavailable
hyper candles ETH 1h --limit 24
hyper funding ETH --hours 24
HYPERLIQUID_NETWORK=testnet hyper price ETH

# Algo framework
hyper algo strategies
hyper algo template grid > grid_strategy.json
hyper algo signal grid_strategy.json --price 2300 --previous-price 2400
hyper algo backtest grid_strategy.json --limit 200

# Real-time feeds
hyper feed prices --coins ETH,BTC
hyper feed prices --coins GOLD --dex xyz
hyper feed book GOLD --dex xyz --depth 5
hyper feed trades GOLD --dex xyz
hyper feed account --fills --orders
hyper feed strategy grid_strategy.json

# General
hyper status 123456
hyper cancel-all --yes
```

For the full command reference, see [docs/COMMANDS.md](docs/COMMANDS.md).

## Project Structure

```
hyperliquid/
├── pyproject.toml          # Dependencies and CLI entry point
├── config.json.example     # Credential template
├── hyper_cli/
│   ├── __init__.py
│   ├── main.py             # Root CLI app (router + shared commands)
│   ├── spot.py             # Spot trading commands
│   ├── perp.py             # Perpetual trading commands
│   ├── account.py          # Account management commands
│   ├── algo.py             # Algotrading framework commands
│   ├── feed.py             # Real-time WebSocket feed commands
│   ├── strategies.py       # Strategy base class and built-ins
│   ├── backtest.py         # Candle-close backtesting engine
│   ├── market.py           # Shared market data helpers
│   ├── client.py           # SDK client initialization
│   ├── config.py           # Config loading and validation
│   └── display.py          # Rich output formatting
├── examples/
│   ├── grid_strategy.json   # Example JSON strategy config
│   └── dca_strategy.yaml    # Example YAML strategy config
└── docs/
    └── COMMANDS.md          # Full command reference
```

## Security

- **`config.json` is gitignored** — your private keys are never committed to the repository
- Use an **API agent wallet** instead of your main wallet's private key. Generate one at [app.hyperliquid.xyz/API](https://app.hyperliquid.xyz/API)
- The API agent can only trade — it cannot withdraw funds from your account
- Leave `main_wallet_secret_key` blank unless you need account actions that require the main wallet signature
- Fund-moving, market-order, modify, and bulk-cancel commands prompt for confirmation unless `--yes` is passed
- Spot/perp market orders and modify commands support `--dry-run` to preview the exact action without signing
- Fund-moving amounts are parsed as Decimal USDC strings: no scientific notation, greater than zero, and at most 6 decimal places
- `hyper perp modify` requires an explicit `--reduce-only` or `--not-reduce-only`
- SDK action responses are parsed; failed top-level statuses, per-order errors, and unknown statuses exit non-zero
- `hyper feed strategy --execute` is intentionally disabled; run without `--execute` for dry-run live candle signals
- Never share your `config.json` or commit it to any repository

## License

MIT
