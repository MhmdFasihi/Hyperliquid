# Hyperliquid Trading CLI

A command-line interface for trading on [Hyperliquid DEX](https://hyperliquid.xyz) — spot and perpetual markets.

Built on top of the official [hyperliquid-python-sdk](https://github.com/hyperliquid-dex/hyperliquid-python-sdk).

## Features

**Spot Trading**
- Limit buy/sell orders with GTC, IOC, ALO time-in-force
- Market buy/sell orders with configurable slippage
- Cancel, cancel-all, and modify orders
- View balances and open orders

**Perpetual Trading**
- Long/short limit orders
- Market open/close positions (full or partial)
- Take-profit and stop-loss orders
- Leverage management (cross and isolated margin)
- View positions, margin summary, and open orders

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

```bash
cp config.json.example config.json
```

Edit `config.json` with your API agent credentials:

```json
{
    "secret_key": "0xYOUR_AGENT_PRIVATE_KEY",
    "account_address": "0xYOUR_MAIN_WALLET_ADDRESS"
}
```

- `secret_key` — Your API agent's private key (generated at [app.hyperliquid.xyz/API](https://app.hyperliquid.xyz/API))
- `account_address` — Your main wallet's public address

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
hyper spot market-buy PURR/USDC 100
hyper spot balances
hyper spot orders

# Perp trading
hyper perp long ETH 0.2 1100
hyper perp short BTC 0.01 100000 --tif alo
hyper perp market-open ETH buy 0.1 --slippage 0.01
hyper perp market-close ETH
hyper perp tp ETH sell 0.2 3500 --trigger 3400
hyper perp sl ETH sell 0.2 2500 --trigger 2600
hyper perp leverage ETH 10
hyper perp leverage ETH 5 --isolated
hyper perp positions

# General
hyper status 123456
hyper cancel-all
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
│   ├── client.py           # SDK client initialization
│   ├── config.py           # Config loading and validation
│   └── display.py          # Rich output formatting
└── docs/
    ├── COMMANDS.md          # Full command reference
    └── ROADMAP.md           # Development roadmap
```

## Security

- **`config.json` is gitignored** — your private keys are never committed to the repository
- Use an **API agent wallet** instead of your main wallet's private key. Generate one at [app.hyperliquid.xyz/API](https://app.hyperliquid.xyz/API)
- The API agent can only trade — it cannot withdraw funds from your account
- Never share your `config.json` or commit it to any repository

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the full development roadmap.

## License

MIT
