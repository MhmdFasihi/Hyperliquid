# Command Reference

## Global Commands

### `hyper status <OID>`

Check the status of any order (spot or perp) by its order ID.

```bash
hyper status 123456
```

### `hyper cancel-all`

Cancel ALL open orders across both spot and perp markets.

```bash
hyper cancel-all
```

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
```

**Options:**
- `--slippage` — Slippage tolerance as decimal (default: `0.05` = 5%)

### `hyper spot market-sell <COIN> <SIZE>`

Place a spot market sell order. Same as `market-buy`.

```bash
hyper spot market-sell PURR/USDC 100
```

### `hyper spot cancel <COIN> <OID>`

Cancel a specific spot order.

```bash
hyper spot cancel PURR/USDC 123456
```

### `hyper spot cancel-all <COIN>`

Cancel all open spot orders for a specific coin.

```bash
hyper spot cancel-all PURR/USDC
```

### `hyper spot modify <OID> <COIN> <SIDE> <SIZE> <PRICE>`

Modify an existing spot order.

```bash
hyper spot modify 123456 PURR/USDC buy 30 0.48
hyper spot modify 123456 PURR/USDC sell 20 0.55 --tif alo
```

**Arguments:**
- `OID` — Order ID to modify
- `COIN` — Spot pair name
- `SIDE` — `buy` or `sell`
- `SIZE` — New order size
- `PRICE` — New limit price

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
```

### `hyper perp short <COIN> <SIZE> <PRICE>`

Place a limit short (sell) order.

```bash
hyper perp short ETH 0.2 4500
hyper perp short SOL 10 200 --tif ioc
```

### `hyper perp market-open <COIN> <SIDE> <SIZE>`

Market open a perp position.

```bash
hyper perp market-open ETH buy 0.1
hyper perp market-open BTC sell 0.01 --slippage 0.005   # 0.5% slippage
```

**Arguments:**
- `COIN` — Perp coin (e.g., `ETH`, `BTC`)
- `SIDE` — `buy`/`long` or `sell`/`short`
- `SIZE` — Position size

**Options:**
- `--slippage` — Slippage tolerance (default: `0.01` = 1%)

### `hyper perp market-close <COIN>`

Market close a perp position. Closes the full position by default.

```bash
hyper perp market-close ETH
hyper perp market-close ETH --size 0.05    # partial close
hyper perp market-close ETH --slippage 0.005
```

**Options:**
- `--size` — Partial close size (omit to close entire position)
- `--slippage` — Slippage tolerance (default: `0.01` = 1%)

### `hyper perp tp <COIN> <SIDE> <SIZE> <PRICE> --trigger <PRICE>`

Place a take-profit order (reduce only).

```bash
# Close a long position when price hits 3400, filling as market order
hyper perp tp ETH sell 0.2 3500 --trigger 3400
```

**Arguments:**
- `COIN` — Perp coin
- `SIDE` — `sell` (to close a long) or `buy` (to close a short)
- `SIZE` — Order size
- `PRICE` — Worst-case fill price

**Options:**
- `--trigger` — **Required.** Price at which the TP order triggers

### `hyper perp sl <COIN> <SIDE> <SIZE> <PRICE> --trigger <PRICE>`

Place a stop-loss order (reduce only).

```bash
# Close a long position when price drops to 2600
hyper perp sl ETH sell 0.2 2500 --trigger 2600
```

Same arguments as `tp`, but triggers as a stop-loss.

### `hyper perp leverage <COIN> <VALUE>`

Set leverage for a perp coin.

```bash
hyper perp leverage ETH 10              # 10x cross margin (default)
hyper perp leverage ETH 5 --isolated    # 5x isolated margin
```

**Arguments:**
- `COIN` — Perp coin
- `VALUE` — Leverage multiplier

**Options:**
- `--isolated` — Use isolated margin instead of cross (default: cross)

### `hyper perp cancel <COIN> <OID>`

Cancel a specific perp order.

```bash
hyper perp cancel ETH 123456
```

### `hyper perp cancel-all <COIN>`

Cancel all open perp orders for a coin.

```bash
hyper perp cancel-all ETH
```

### `hyper perp modify <OID> <COIN> <SIDE> <SIZE> <PRICE>`

Modify an existing perp order.

```bash
hyper perp modify 123456 ETH buy 0.1 1105
```

### `hyper perp positions`

View all open perp positions with account margin summary.

```bash
hyper perp positions
```

Shows: Coin, Side (Long/Short), Size, Entry Price, Unrealized PnL, Leverage, Liquidation Price, Margin Used.

### `hyper perp orders [COIN]`

View open perp orders. Optionally filter by coin.

```bash
hyper perp orders
hyper perp orders ETH
```

### `hyper perp status <OID>`

Check a specific perp order status.

```bash
hyper perp status 123456
```

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
