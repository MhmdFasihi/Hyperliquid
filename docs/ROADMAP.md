# Development Roadmap

## Phase 1: Spot Trading CLI — DONE

- [x] Project setup (conda env, pyproject.toml, git repo)
- [x] Config management (config.json with API agent credentials)
- [x] Spot limit orders (buy/sell with GTC, IOC, ALO)
- [x] Spot market orders (buy/sell with slippage control)
- [x] Order management (cancel, cancel-all, modify)
- [x] Query commands (balances, open orders, order status)
- [x] Rich formatted output (colored tables)

## Phase 2: Perpetual Trading CLI — DONE

- [x] Limit long/short orders
- [x] Market open/close positions
- [x] Take-profit and stop-loss orders
- [x] Leverage management (cross and isolated margin)
- [x] Position viewer with margin summary
- [x] Perp order management (cancel, modify, orders)
- [x] CLI restructured into subcommand groups (spot/perp)
- [x] Comprehensive documentation

## Phase 3: Account Management

- [ ] Transfer USDC between spot and perp (`hyper transfer spot-to-perp 100`)
- [ ] Withdraw USDC
- [ ] View transaction history
- [ ] Sub-account support

## Phase 4: Market Data

- [ ] Live prices (`hyper price ETH`)
- [ ] Order book snapshot (`hyper book ETH`)
- [ ] OHLCV candles (`hyper candles ETH 1h`)
- [ ] Funding rates (`hyper funding ETH`)
- [ ] All mid prices (`hyper prices`)

## Phase 5: Algotrading Framework

- [ ] Strategy base class
- [ ] Signal generation framework
- [ ] Basic strategies (grid, TWAP, DCA)
- [ ] Backtesting engine
- [ ] Strategy configuration via YAML/JSON

## Phase 6: Real-Time Feeds

- [ ] WebSocket price feeds
- [ ] Real-time order book updates
- [ ] Trade stream
- [ ] Account event notifications
- [ ] Strategy live execution with WebSocket triggers
