# Command Reference

## Global Commands

### `hyper status <OID>`

Check the status of any order (spot or perp) by its order ID.

```bash
hyper status 123456
```

### `hyper cancel-all`

Cancel ALL open orders across both spot and perp markets. Prompts for confirmation unless `--yes` is passed.

```bash
hyper cancel-all --yes
```

This shared command uses the default SDK order namespace. Use `hyper perp cancel-all <COIN> --dex <DEX>` for builder-deployed perp markets.

---

## Market Data Commands

Public market and feed commands use mainnet by default. Set `HYPERLIQUID_NETWORK=testnet` to use Hyperliquid testnet for read-only checks:

```bash
HYPERLIQUID_NETWORK=testnet hyper price ETH
HYPERLIQUID_NETWORK=testnet hyper feed prices --coins ETH --updates 1
```

### `hyper price <COIN>`

Show the current mid price for a perp coin or spot pair.

```bash
hyper price ETH
hyper price PURR/USDC
hyper price ETH --dex builder-dex
```

**Options:**
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper prices`

Show current mid prices for all actively traded markets.

```bash
hyper prices
hyper prices --dex builder-dex
```

**Options:**
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper book <COIN>`

Show an L2 order book snapshot.

```bash
hyper book ETH
hyper book ETH --depth 20
hyper book ETH --dex builder-dex
hyper book GOLD --dex xyz
hyper book BRENTOIL --dex xyz
```

**Options:**
- `--depth`, `-d` — Number of price levels per side (default: `10`)
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper candles <COIN> <INTERVAL>`

Show OHLCV candle snapshots.

```bash
hyper candles ETH 1h
hyper candles BTC 5m --limit 50
hyper candles ETH 1h --dex builder-dex
```

**Arguments:**
- `COIN` — Perp coin or spot pair
- `INTERVAL` — Candle interval: `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `8h`, `12h`, `1d`, `3d`, `1w`, `1M`

**Options:**
- `--limit`, `-n` — Number of candles to request (default: `24`)
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper funding <COIN>`

Show current and historical funding rates for a perp coin.

```bash
hyper funding ETH
hyper funding BTC --hours 48
hyper funding GOLD --dex xyz
```

**Options:**
- `--hours`, `-h` — Funding history lookback in hours (default: `24`)
- `--dex` — Perp DEX name for builder-deployed markets

For builder-deployed markets, pass the DEX name in lowercase or uppercase with `--dex`; commands normalize it before constructing SDK clients and symbols.
`BRENTOIL` and `WTIOIL` are different markets; `WTIOIL` is not remapped to `BRENTOIL`.

---

## Spot Commands (`hyper spot`)

### `hyper spot buy <COIN> <SIZE> <PRICE>`

Place a spot limit buy order.

```bash
hyper spot buy PURR/USDC 24 0.5
hyper spot buy PURR/USDC 24 0.5 --tif alo    # post-only
hyper spot buy PURR/USDC 24 0.5 --tif ioc    # immediate-or-cancel
```

**Arguments:**
- `COIN` — Spot pair name (e.g., `PURR/USDC`)
- `SIZE` — Order quantity
- `PRICE` — Limit price

**Options:**
- `--tif` — Time in force: `gtc` (default), `ioc`, `alo`

### `hyper spot sell <COIN> <SIZE> <PRICE>`

Place a spot limit sell order. Same arguments as `buy`.

```bash
hyper spot sell PURR/USDC 24 0.51
```

### `hyper spot market-buy <COIN> <SIZE>`

Place a spot market buy order.

```bash
hyper spot market-buy PURR/USDC 100
hyper spot market-buy PURR/USDC 100 --slippage 0.03   # 3% slippage
hyper spot market-buy PURR/USDC 100 --dry-run
hyper spot market-buy PURR/USDC 100 --yes
```

**Options:**
- `--slippage` — Slippage tolerance as decimal from `0` to `1` (default: `0.05` = 5%)
- `--yes`, `-y` — Skip confirmation prompt
- `--dry-run` — Print the action without signing or placing an order

### `hyper spot market-sell <COIN> <SIZE>`

Place a spot market sell order. Same as `market-buy`.

```bash
hyper spot market-sell PURR/USDC 100
hyper spot market-sell PURR/USDC 100 --dry-run
```

### `hyper spot cancel <COIN> <OID>`

Cancel a specific spot order.

```bash
hyper spot cancel PURR/USDC 123456
```

### `hyper spot cancel-all <COIN>`

Cancel all open spot orders for a specific coin. Prompts for confirmation unless `--yes` is passed.

```bash
hyper spot cancel-all PURR/USDC --yes
```

### `hyper spot modify <OID> <COIN> <SIDE> <SIZE> <PRICE>`

Modify an existing spot order.

```bash
hyper spot modify 123456 PURR/USDC buy 30 0.48
hyper spot modify 123456 PURR/USDC sell 20 0.55 --tif alo
hyper spot modify 123456 PURR/USDC buy 30 0.48 --dry-run
```

**Arguments:**
- `OID` — Order ID to modify
- `COIN` — Spot pair name
- `SIDE` — `buy` or `sell`
- `SIZE` — New order size
- `PRICE` — New limit price

**Options:**
- `--tif` — Time in force: `gtc` (default), `ioc`, `alo`
- `--yes`, `-y` — Skip confirmation prompt
- `--dry-run` — Print the replacement order without signing

### `hyper spot orders [COIN]`

View open spot orders. Optionally filter by coin.

```bash
hyper spot orders              # all open orders
hyper spot orders PURR/USDC    # orders for PURR/USDC only
```

### `hyper spot balances`

View spot token balances.

```bash
hyper spot balances
```

### `hyper spot status <OID>`

Check a specific spot order status.

```bash
hyper spot status 123456
```

---

## Perp Commands (`hyper perp`)

### `hyper perp long <COIN> <SIZE> <PRICE>`

Place a limit long (buy) order.

```bash
hyper perp long ETH 0.2 1100
hyper perp long BTC 0.01 50000 --tif alo
hyper perp long GOLD 1 3000 --dex xyz
```

**Options:**
- `--tif` — Time in force: `gtc` (default), `ioc`, `alo`
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper perp short <COIN> <SIZE> <PRICE>`

Place a limit short (sell) order.

```bash
hyper perp short ETH 0.2 4500
hyper perp short SOL 10 200 --tif ioc
hyper perp short GOLD 1 3500 --dex xyz
```

### `hyper perp market-open <COIN> <SIDE> <SIZE>`

Market open a perp position.

```bash
hyper perp market-open ETH buy 0.1
hyper perp market-open BTC sell 0.01 --slippage 0.005   # 0.5% slippage
hyper perp market-open GOLD buy 1 --dex xyz --dry-run
hyper perp market-open ETH buy 0.1 --yes
```

**Arguments:**
- `COIN` — Perp coin (e.g., `ETH`, `BTC`)
- `SIDE` — `buy`/`long` or `sell`/`short`
- `SIZE` — Position size

**Options:**
- `--slippage` — Slippage tolerance as decimal from `0` to `1` (default: `0.01` = 1%)
- `--yes`, `-y` — Skip confirmation prompt
- `--dry-run` — Print the action without signing or placing an order
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper perp market-close <COIN>`

Market close a perp position. Closes the full position by default.

```bash
hyper perp market-close ETH
hyper perp market-close ETH --size 0.05    # partial close
hyper perp market-close ETH --slippage 0.005
hyper perp market-close GOLD --dex xyz
```

**Options:**
- `--size` — Partial close size (omit to close entire position)
- `--slippage` — Slippage tolerance as decimal from `0` to `1` (default: `0.01` = 1%)
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper perp tp <COIN> <SIDE> <SIZE> <PRICE> --trigger <PRICE>`

Place a take-profit order (reduce only).

```bash
# Close a long position when price hits 3400, filling as market order
hyper perp tp ETH sell 0.2 3500 --trigger 3400
hyper perp tp GOLD sell 1 3400 --trigger 3300 --dex xyz
```

**Arguments:**
- `COIN` — Perp coin
- `SIDE` — `sell` (to close a long) or `buy` (to close a short)
- `SIZE` — Order size
- `PRICE` — Worst-case fill price

**Options:**
- `--trigger` — **Required.** Price at which the TP order triggers
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper perp sl <COIN> <SIDE> <SIZE> <PRICE> --trigger <PRICE>`

Place a stop-loss order (reduce only).

```bash
# Close a long position when price drops to 2600
hyper perp sl ETH sell 0.2 2500 --trigger 2600
hyper perp sl GOLD sell 1 2800 --trigger 2900 --dex xyz
```

Same arguments and options as `tp`, but triggers as a stop-loss.

### `hyper perp leverage <COIN> <VALUE>`

Set leverage for a perp coin.

```bash
hyper perp leverage ETH 10              # 10x cross margin (default)
hyper perp leverage ETH 5 --isolated    # 5x isolated margin
hyper perp leverage GOLD 3 --dex xyz
```

**Arguments:**
- `COIN` — Perp coin
- `VALUE` — Leverage multiplier from `1` to `50`

**Options:**
- `--isolated` — Use isolated margin instead of cross (default: cross)
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper perp cancel <COIN> <OID>`

Cancel a specific perp order.

```bash
hyper perp cancel ETH 123456
hyper perp cancel GOLD 123456 --dex xyz
```

**Options:**
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper perp cancel-all <COIN>`

Cancel all open perp orders for a coin. Prompts for confirmation unless `--yes` is passed.

```bash
hyper perp cancel-all ETH --yes
hyper perp cancel-all GOLD --dex xyz --yes
```

**Options:**
- `--yes`, `-y` — Skip confirmation prompt
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper perp modify <OID> <COIN> <SIDE> <SIZE> <PRICE>`

Modify an existing perp order.

```bash
hyper perp modify 123456 ETH buy 0.1 1105 --not-reduce-only
hyper perp modify 123456 ETH sell 0.1 3200 --reduce-only --dry-run
hyper perp modify 123456 GOLD buy 1 3000 --not-reduce-only --dex xyz
```

`hyper perp modify` requires an explicit `--reduce-only` or `--not-reduce-only` so the replacement order cannot silently change exposure semantics.

**Options:**
- `--tif` — Time in force: `gtc` (default), `ioc`, `alo`
- `--reduce-only` / `--not-reduce-only` — Required explicit reduce-only mode
- `--yes`, `-y` — Skip confirmation prompt
- `--dry-run` — Print the replacement order without signing
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper perp positions`

View all open perp positions with account margin summary.

```bash
hyper perp positions
hyper perp positions --dex xyz
```

Shows: Coin, Side (Long/Short), Size, Entry Price, Unrealized PnL, Leverage, Liquidation Price, Margin Used.

### `hyper perp orders [COIN]`

View open perp orders. Optionally filter by coin.

```bash
hyper perp orders
hyper perp orders ETH
hyper perp orders GOLD --dex xyz
```

**Options:**
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper perp status <OID>`

Check a specific perp order status.

```bash
hyper perp status 123456
```

Order status lookups are SDK OID lookups and remain default-account scoped; use market/order list commands with `--dex` when you need per-DEX open-order views.

---

## Account Commands (`hyper account`)

Fund-moving and sub-account mutation commands require `main_wallet_secret_key` in `config.json`. They prompt for confirmation unless `--yes` is passed.

USDC amounts are parsed as Decimal strings. Use normal decimal notation greater than zero, with at most 6 decimal places; scientific notation such as `1e-6` is rejected.

### `hyper account spot-to-perp <AMOUNT>`

Transfer USDC from spot to perp account.

```bash
hyper account spot-to-perp 100 --yes
```

**Options:**
- `--yes`, `-y` — Skip confirmation prompt

### `hyper account perp-to-spot <AMOUNT>`

Transfer USDC from perp to spot account.

```bash
hyper account perp-to-spot 50 --yes
```

**Options:**
- `--yes`, `-y` — Skip confirmation prompt

### `hyper account withdraw <AMOUNT>`

Withdraw USDC to an on-chain address. If `--to` is omitted, the configured account address is used.

```bash
hyper account withdraw 100 --to 0xabc... --yes
hyper account withdraw 25 --yes
```

**Options:**
- `--to` — Destination address
- `--yes`, `-y` — Skip confirmation prompt

### `hyper account history`

View non-funding transaction history.

```bash
hyper account history
hyper account history --days 30
```

**Options:**
- `--days`, `-d` — Look back N days (default: `7`)

### `hyper account sub-accounts`

List all sub-accounts.

```bash
hyper account sub-accounts
```

### `hyper account sub-create <NAME>`

Create a new sub-account.

```bash
hyper account sub-create trading-bot --yes
```

**Options:**
- `--yes`, `-y` — Skip confirmation prompt

### `hyper account sub-transfer <SUB_ADDRESS> <AMOUNT> <DIRECTION>`

Transfer USDC to or from a sub-account.

```bash
hyper account sub-transfer 0xabc... 100 deposit --yes
hyper account sub-transfer 0xabc... 50 withdraw --yes
```

**Arguments:**
- `SUB_ADDRESS` — Sub-account address
- `AMOUNT` — USDC amount
- `DIRECTION` — `deposit`/`in` or `withdraw`/`out`

**Options:**
- `--yes`, `-y` — Skip confirmation prompt

---

## Algo Commands (`hyper algo`)

The algo commands provide dry-run signal generation and candle-close backtesting. Live automated execution is disabled in this release; `hyper feed strategy` emits live dry-run signals only.

### `hyper algo strategies`

List built-in strategies and their required parameters.

```bash
hyper algo strategies
```

### `hyper algo template <STRATEGY>`

Print a starter strategy config.

```bash
hyper algo template grid
hyper algo template dca --format yaml
hyper algo template grid > grid_strategy.json
```

**Arguments:**
- `STRATEGY` — `grid`, `twap`, or `dca`

**Options:**
- `--format`, `-f` — Output format: `json` or `yaml` (default: `json`)

### `hyper algo signal <CONFIG>`

Generate the next signal from a JSON or YAML strategy config.

```bash
hyper algo signal grid_strategy.json --price 2300 --previous-price 2400
hyper algo signal dca_strategy.yaml --price 2300 --step 24
```

**Options:**
- `--price`, `-p` — Use this price instead of fetching the current mid
- `--previous-price` — Previous price for crossing strategies such as grid
- `--step` — Strategy step index for TWAP/DCA (default: `0`)
- `--position` — Current base-asset position (default: `0`)

### `hyper algo backtest <CONFIG>`

Backtest a strategy over historical candle closes using public candle data. The engine avoids same-candle lookahead: first it processes orders emitted by earlier candles, then it emits the current close signal. Market signals fill on the next candle open with optional `backtest.slippage_bps`; limit signals rest until a later candle high/low touches the limit price.

```bash
hyper algo backtest grid_strategy.json --limit 200
hyper algo backtest dca_strategy.yaml --limit 300 --trades 20
```

**Options:**
- `--limit`, `-n` — Number of candles to fetch (defaults to `backtest.limit` in config, then `200`)
- `--start-ms` — Start time in Unix milliseconds
- `--end-ms` — End time in Unix milliseconds
- `--trades` — Number of recent trades to print (default: `10`)

### Strategy Config Example

```json
{
  "strategy": "grid",
  "coin": "ETH",
  "market_type": "perp",
  "interval": "1h",
  "params": {
    "lower_price": 2200,
    "upper_price": 2600,
    "levels": 5,
    "order_size": 0.02
  },
  "backtest": {
    "starting_cash": 10000,
    "fee_rate": 0.00035,
    "slippage_bps": 1,
    "limit": 200
  }
}
```

The `examples/` directory contains source-tree samples. For installed usage, prefer `hyper algo template ... > my_strategy.json`.

Built-in strategies:

| Strategy | Behavior |
| --- | --- |
| `grid` | Buys when price crosses down a grid level; sells inventory when price crosses up |
| `twap` | Splits one target order into equal slices across sequential candles |
| `dca` | Emits a fixed-size order every N candles until `max_orders` is reached |

---

## Real-Time Feed Commands (`hyper feed`)

These commands use Hyperliquid WebSocket subscriptions. Use `--seconds` or `--updates` to stop automatically, or press `Ctrl-C`.

### `hyper feed prices`

Stream live mid prices.

```bash
hyper feed prices
hyper feed prices --coins ETH,BTC,SOL
hyper feed prices --all --updates 1
hyper feed prices --coins GOLD --dex xyz
```

**Options:**
- `--coins`, `-c` — Comma-separated coins to print (default: `BTC,ETH,SOL`)
- `--all` — Print every received mid price
- `--seconds`, `-s` — Stop after N seconds
- `--updates`, `-n` — Stop after N updates
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper feed book <COIN>`

Stream live L2 order book updates.

```bash
hyper feed book ETH
hyper feed book PURR/USDC --depth 3 --updates 5
hyper feed book GOLD --dex xyz --depth 3
```

**Options:**
- `--depth`, `-d` — Number of price levels per side (default: `5`)
- `--seconds`, `-s` — Stop after N seconds
- `--updates`, `-n` — Stop after N updates
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper feed trades <COIN>`

Stream live trades.

```bash
hyper feed trades ETH
hyper feed trades BTC --seconds 30
hyper feed trades GOLD --dex xyz
```

**Options:**
- `--seconds`, `-s` — Stop after N seconds
- `--updates`, `-n` — Stop after N WebSocket messages
- `--dex` — Perp DEX name for builder-deployed markets

### `hyper feed account`

Stream user events, order updates, and fills for the configured account.

```bash
hyper feed account
hyper feed account --fills --orders --updates 5
hyper feed account --events --include-snapshots --updates 1
```

**Options:**
- `--seconds`, `-s` — Stop after N seconds
- `--updates`, `-n` — Stop after N events
- `--events` — Subscribe to user events
- `--orders` — Subscribe to order updates
- `--fills` — Subscribe to user fills
- `--include-snapshots` — Print and count snapshot messages

If none of `--events`, `--orders`, or `--fills` is selected, all three streams are subscribed. Snapshot messages are skipped by default.

### `hyper feed strategy <CONFIG>`

Run a strategy from live candle WebSocket triggers. By default this is dry-run signal generation only and processes closed candles by waiting until the next candle timestamp arrives.

```bash
hyper feed strategy dca_strategy.yaml
hyper feed strategy grid_strategy.json --position 0.02 --updates 10
hyper feed strategy grid_strategy.json --dex xyz --updates 10
```

Live order placement is currently disabled. Passing `--execute` exits before loading config or placing orders:

```bash
hyper feed strategy dca_strategy.yaml --execute
```

**Options:**
- `--seconds`, `-s` — Stop after N seconds
- `--updates`, `-n` — Stop after N processed candles
- `--position` — Initial local base-asset position
- `--step` — Initial strategy step index
- `--every-update` — Process every candle update instead of only new candle timestamps
- `--execute` — Disabled; exits with a clear error
- `--yes` — Reserved for future execution support
- `--slippage` — Reserved for future execution support, from `0` to `1` (default: `0.01`)
- `--max-orders` — Reserved for future execution support
- `--max-notional` — Reserved for future execution support
- `--max-position` — Reserved for future execution support
- `--cooldown-seconds` — Reserved for future execution support
- `--dex` — Perp DEX name for builder-deployed markets

Use `--every-update` only when you intentionally want dry-run signals on in-progress candle updates.

---

## Safety Rules

- Numeric CLI and strategy config inputs reject `nan`, `inf`, negative values where invalid, and out-of-range slippage or leverage.
- SDK action responses are parsed. Top-level failures, per-order errors, and unknown status shapes exit non-zero.
- Market orders and modify commands prompt unless `--yes` is passed, and they support `--dry-run` previews.
- Limit open orders remain immediate.
- `hyper cancel-all` prints its success count only after the SDK response parses as successful.

---

## Order Types Explained

| TIF | Name | Behavior |
| --- | --- | --- |
| `gtc` | Good-Till-Cancelled | Rests on the book until filled or cancelled |
| `ioc` | Immediate-Or-Cancel | Fills immediately or cancels unfilled portion |
| `alo` | Add-Liquidity-Only | Post-only; rejected if it would immediately fill |

## TP/SL Workflow Example

Open a long, then set TP and SL:

```bash
# 1. Open long position
hyper perp long ETH 0.2 3000

# 2. Set take-profit at 3400 (close by selling)
hyper perp tp ETH sell 0.2 3500 --trigger 3400

# 3. Set stop-loss at 2800 (close by selling)
hyper perp sl ETH sell 0.2 2700 --trigger 2800
```

For a short position, reverse the sides:

```bash
hyper perp short ETH 0.2 3500
hyper perp tp ETH buy 0.2 3000 --trigger 3100     # TP below entry
hyper perp sl ETH buy 0.2 3800 --trigger 3700      # SL above entry
```
