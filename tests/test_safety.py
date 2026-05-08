import unittest
from math import inf, nan

import typer
from typer.testing import CliRunner

from hyper_cli import account, client as client_module, feed, main, perp, spot
from hyper_cli.backtest import run_backtest
from hyper_cli.display import format_side, format_time_ms, print_order_response
from hyper_cli.market import find_mid, normalize_coin
from hyper_cli.responses import parse_action_response
from hyper_cli.strategies import BaseStrategy, MarketSnapshot, Signal, SignalAction, StrategyConfig, StrategyState
from hyper_cli.validation import parse_side, parse_usdc_amount, require_address, require_positive, require_slippage, usdc_to_micro


class FakeExchange:
    def __init__(self):
        self.market_close_args = None
        self.market_open_args = None
        self.sub_transfer_args = None
        self.usd_class_transfer_args = None
        self.order_args = None
        self.modify_order_args = None
        self.cancel_args = None
        self.bulk_cancel_args = None
        self.response = {"status": "ok"}

    def market_close(self, *args, **kwargs):
        self.market_close_args = (args, kwargs)
        return self.response

    def market_open(self, *args, **kwargs):
        self.market_open_args = (args, kwargs)
        return self.response

    def usd_class_transfer(self, *args, **kwargs):
        self.usd_class_transfer_args = (args, kwargs)
        return self.response

    def sub_account_transfer(self, *args, **kwargs):
        self.sub_transfer_args = (args, kwargs)
        return self.response

    def order(self, *args, **kwargs):
        self.order_args = (args, kwargs)
        return self.response

    def modify_order(self, *args, **kwargs):
        self.modify_order_args = (args, kwargs)
        return self.response

    def cancel(self, *args, **kwargs):
        self.cancel_args = (args, kwargs)
        return self.response

    def bulk_cancel(self, *args, **kwargs):
        self.bulk_cancel_args = (args, kwargs)
        return self.response

    def _slippage_price(self, name, is_buy, slippage, px=None):
        return 99.0


class FakeInfo:
    name_to_coin = {"xyz:GOLD": "xyz:GOLD"}

    def __init__(self):
        self.open_orders_response = [{"coin": "ETH", "oid": 123}]

    def open_orders(self, *args, **kwargs):
        return self.open_orders_response


class FakeWsInfo(FakeInfo):
    def __init__(self):
        super().__init__()
        self.subscriptions = []
        self.disconnected = False

    def subscribe(self, subscription, callback):
        self.subscriptions.append(subscription)
        callback({"data": {"mids": {"xyz:GOLD": "3000", "ETH": "2000"}}})
        return len(self.subscriptions)

    def disconnect_websocket(self):
        self.disconnected = True


class FakeClient:
    def __init__(self):
        self.address = "0x0000000000000000000000000000000000000001"
        self.exchange = FakeExchange()
        self.main_wallet_exchange = self.exchange
        self.info = FakeInfo()

    def exchange_for_dex(self, dex):
        return self.exchange

    def info_for_dex(self, dex):
        return self.info


class LimitBuyStrategy(BaseStrategy):
    name = "limit-buy"

    def validate(self) -> None:
        pass

    def generate_signal(self, snapshot: MarketSnapshot, state: StrategyState) -> Signal:
        return Signal(SignalAction.BUY, self.coin, size=1.0, price=100.0, order_type="limit")


class MarketBuyOnceStrategy(BaseStrategy):
    name = "market-buy-once"

    def validate(self) -> None:
        pass

    def generate_signal(self, snapshot: MarketSnapshot, state: StrategyState) -> Signal:
        if state.step == 0:
            return Signal(SignalAction.BUY, self.coin, size=1.0, order_type="market")
        return Signal(SignalAction.HOLD, self.coin)


class SafetyTests(unittest.TestCase):
    def test_sdk_response_parser_classifies_statuses(self):
        self.assertFalse(parse_action_response({"status": "err", "response": "bad"}).ok)

        resting = parse_action_response({"status": "ok", "response": {"data": {"statuses": [{"resting": {"oid": 1}}]}}})
        self.assertTrue(resting.ok)
        self.assertEqual(resting.resting_count, 1)

        cancel_success = parse_action_response({"status": "ok", "response": {"data": {"statuses": ["success"]}}})
        self.assertTrue(cancel_success.ok)
        self.assertEqual(cancel_success.success_count, 1)

        filled = parse_action_response(
            {"status": "ok", "response": {"data": {"statuses": [{"filled": {"totalSz": "1.5"}}]}}}
        )
        self.assertTrue(filled.ok)
        self.assertEqual(filled.filled_count, 1)
        self.assertEqual(filled.filled_size, 1.5)

        error = parse_action_response({"status": "ok", "response": {"data": {"statuses": [{"error": "rejected"}]}}})
        self.assertFalse(error.ok)
        self.assertEqual(error.error_count, 1)

    def test_market_close_uses_size_keyword(self):
        fake = FakeClient()
        original_get_client = perp.get_client
        try:
            perp.get_client = lambda: fake
            perp.market_close("ETH", size=0.05, slippage=0.01)
        finally:
            perp.get_client = original_get_client

        args, kwargs = fake.exchange.market_close_args
        self.assertEqual(args, ("ETH",))
        self.assertEqual(kwargs, {"sz": 0.05, "slippage": 0.01})

    def test_invalid_side_is_rejected(self):
        with self.assertRaises(typer.Exit):
            parse_side("buuy")

    def test_slippage_is_bounded(self):
        with self.assertRaises(typer.Exit):
            require_slippage("slippage", 1.01)

    def test_nan_and_inf_are_rejected(self):
        for value in (nan, inf, -inf):
            with self.assertRaises(typer.Exit):
                require_positive("size", value)
            with self.assertRaises(typer.Exit):
                require_slippage("slippage", value)

    def test_decimal_usdc_parsing_and_micro_conversion(self):
        amount = parse_usdc_amount("amount", "1.230000")
        self.assertEqual(usdc_to_micro(amount), 1_230_000)
        with self.assertRaises(typer.Exit):
            parse_usdc_amount("amount", "1e-6")
        with self.assertRaises(typer.Exit):
            parse_usdc_amount("amount", "1.1234567")

    def test_address_validation(self):
        require_address("destination", "0x0000000000000000000000000000000000000001")
        with self.assertRaises(typer.Exit):
            require_address("destination", "0xabc")

    def test_sub_transfer_uses_human_usdc_units(self):
        fake = FakeClient()
        original_get_client = account.get_client
        try:
            account.get_client = lambda: fake
            account.sub_transfer("0x0000000000000000000000000000000000000001", "1.23", "deposit", yes=True)
        finally:
            account.get_client = original_get_client

        args, _ = fake.exchange.sub_transfer_args
        self.assertEqual(args, ("0x0000000000000000000000000000000000000001", True, 1_230_000))

    def test_sub_transfer_rejects_extra_usdc_decimals(self):
        with self.assertRaises(typer.Exit):
            account._usdc_to_micro("1.1234567")

    def test_account_failed_response_exits(self):
        fake = FakeClient()
        fake.exchange.response = {"status": "err", "response": "bad"}
        original_get_client = account.get_client
        try:
            account.get_client = lambda: fake
            with self.assertRaises(typer.Exit):
                account.spot_to_perp("1", yes=True)
        finally:
            account.get_client = original_get_client

    def test_backtest_limit_order_requires_later_candle_touch(self):
        strategy = LimitBuyStrategy(StrategyConfig(name="limit-buy", coin="ETH"))
        result = run_backtest(
            strategy,
            [{"t": 1, "o": "105", "h": "110", "l": "99", "c": "105", "n": 1, "v": "1"}],
            starting_cash=1000,
        )
        self.assertEqual(len(result.trades), 0)
        self.assertEqual(result.skipped_signals, 1)

        result = run_backtest(
            strategy,
            [
                {"t": 1, "o": "105", "h": "110", "l": "99", "c": "105", "n": 1, "v": "1"},
                {"t": 2, "o": "106", "h": "110", "l": "99", "c": "106", "n": 1, "v": "1"},
            ],
            starting_cash=1000,
        )
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades[0].price, 100.0)

    def test_backtest_market_signal_fills_next_open(self):
        strategy = MarketBuyOnceStrategy(StrategyConfig(name="market-buy-once", coin="ETH"))
        result = run_backtest(
            strategy,
            [
                {"t": 1, "o": "100", "h": "120", "l": "90", "c": "110"},
                {"t": 2, "o": "200", "h": "205", "l": "190", "c": "201"},
            ],
            starting_cash=1000,
            slippage_bps=100,
        )
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades[0].price, 202.0)

    def test_perp_live_sell_is_reduce_only(self):
        fake = FakeClient()
        signal = Signal(SignalAction.SELL, "ETH", size=0.5, order_type="market")
        result = feed._execute_signal(
            fake,
            signal,
            slippage=0.01,
            market_type="perp",
            state=StrategyState(position=1.0),
            current_price=100.0,
        )
        self.assertEqual(result["status"], "ok")
        _, kwargs = fake.exchange.order_args
        self.assertTrue(kwargs["reduce_only"])

    def test_live_sell_cannot_exceed_local_position(self):
        fake = FakeClient()
        signal = Signal(SignalAction.SELL, "ETH", size=2.0, order_type="market")
        with self.assertRaises(RuntimeError):
            feed._execute_signal(
                fake,
                signal,
                slippage=0.01,
                market_type="perp",
                state=StrategyState(position=1.0),
                current_price=100.0,
            )

    def test_failed_perp_order_response_exits(self):
        fake = FakeClient()
        fake.exchange.response = {"status": "ok", "response": {"data": {"statuses": [{"error": "rejected"}]}}}
        original_get_client = perp.get_client
        try:
            perp.get_client = lambda: fake
            with self.assertRaises(typer.Exit):
                perp.long("ETH", 1.0, 100.0)
        finally:
            perp.get_client = original_get_client

    def test_perp_modify_requires_reduce_only_and_passes_choice(self):
        with self.assertRaises(typer.Exit):
            perp.modify(123, "ETH", "buy", 1.0, 100.0, reduce_only=None, yes=True)

        fake = FakeClient()
        original_get_client = perp.get_client
        try:
            perp.get_client = lambda: fake
            perp.modify(123, "ETH", "buy", 1.0, 100.0, reduce_only=False, yes=True)
        finally:
            perp.get_client = original_get_client

        _, kwargs = fake.exchange.modify_order_args
        self.assertFalse(kwargs["reduce_only"])

    def test_feed_strategy_execute_is_disabled_before_config_load(self):
        result = CliRunner().invoke(feed.app, ["strategy", "missing.json", "--execute", "--yes"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--execute is disabled", result.output)

    def test_trade_display_handles_unknown_side_and_bad_timestamp(self):
        self.assertEqual(format_side("X", plain=True), "Unknown (X)")
        self.assertEqual(format_time_ms("bad"), "bad")
        feed._print_trades([{"time": "bad", "coin": "ETH", "side": "X", "sz": "1", "px": "2"}])

    def test_builder_dex_symbol_normalization(self):
        fake_info = FakeInfo()
        self.assertEqual(normalize_coin(fake_info, "GOLD", "XYZ"), "xyz:GOLD")
        self.assertEqual(find_mid({"xyz:GOLD": "3000"}, fake_info.name_to_coin, "GOLD", "XYZ"), ("xyz:GOLD", "3000"))

    def test_order_response_accepts_none(self):
        self.assertFalse(print_order_response(None).ok)

    def test_feed_prices_dex_subscription_includes_dex(self):
        fake = FakeWsInfo()
        original_get_ws_info = feed.get_ws_info
        try:
            feed.get_ws_info = lambda perp_dexs=None: fake
            feed.prices(coins="GOLD", updates=1, dex="XYZ")
        finally:
            feed.get_ws_info = original_get_ws_info

        self.assertEqual(fake.subscriptions, [{"type": "allMids", "dex": "xyz"}])
        self.assertTrue(fake.disconnected)

    def test_get_ws_info_starts_websocket_after_metadata_load(self):
        events = []

        class MetadataFirstInfo:
            def __init__(self, base_url, skip_ws=False, perp_dexs=None):
                events.append(("info", skip_ws, perp_dexs))
                self.base_url = base_url
                self.ws_manager = None

        class StartedWsManager:
            def __init__(self, base_url):
                events.append(("ws_init", base_url))

            def start(self):
                events.append(("ws_start",))

        original_info = client_module.Info
        original_ws_manager = client_module.WebsocketManager
        try:
            client_module.Info = MetadataFirstInfo
            client_module.WebsocketManager = StartedWsManager
            info = client_module.get_ws_info(["xyz"])
        finally:
            client_module.Info = original_info
            client_module.WebsocketManager = original_ws_manager

        self.assertIsInstance(info.ws_manager, StartedWsManager)
        self.assertEqual(events[0], ("info", True, ["xyz"]))
        self.assertEqual(events[1][0], "ws_init")
        self.assertEqual(events[2], ("ws_start",))

    def test_wait_for_stream_disconnects_and_propagates_callback_error(self):
        fake = FakeWsInfo()
        controller = feed.StreamController(updates=None)
        controller.fail(RuntimeError("callback failed"))

        with self.assertRaisesRegex(RuntimeError, "callback failed"):
            feed._wait_for_stream(fake, controller, seconds=1)

        self.assertTrue(fake.disconnected)

    def test_spot_market_dry_run_does_not_load_client(self):
        original_get_client = spot.get_client
        try:
            spot.get_client = lambda: self.fail("dry-run should not create a client")
            spot.market_buy("PURR/USDC", 100.0, dry_run=True)
        finally:
            spot.get_client = original_get_client

    def test_spot_market_failed_response_exits(self):
        fake = FakeClient()
        fake.exchange.response = {"status": "err", "response": "bad"}
        original_get_client = spot.get_client
        try:
            spot.get_client = lambda: fake
            with self.assertRaises(typer.Exit):
                spot.market_buy("PURR/USDC", 100.0, yes=True)
        finally:
            spot.get_client = original_get_client

    def test_account_transfer_uses_canonical_decimal_string(self):
        fake = FakeClient()
        original_get_client = account.get_client
        try:
            account.get_client = lambda: fake
            account.spot_to_perp("1.230000", yes=True)
        finally:
            account.get_client = original_get_client

        args, kwargs = fake.exchange.usd_class_transfer_args
        self.assertEqual(args, ("1.23",))
        self.assertEqual(kwargs, {"to_perp": True})

    def test_root_cancel_all_requires_bulk_cancel_success(self):
        fake = FakeClient()
        fake.exchange.response = {"status": "ok", "response": {"data": {"statuses": [{"error": "already canceled"}]}}}
        original_get_client = main.get_client
        try:
            main.get_client = lambda: fake
            with self.assertRaises(typer.Exit):
                main.cancel_all(yes=True)
        finally:
            main.get_client = original_get_client

        args, _ = fake.exchange.bulk_cancel_args
        self.assertEqual(args, ([{"coin": "ETH", "oid": 123}],))

    def test_perp_cancel_accepts_success_status(self):
        fake = FakeClient()
        fake.exchange.response = {"status": "ok", "response": {"data": {"statuses": ["success"]}}}
        original_get_client = perp.get_client
        try:
            perp.get_client = lambda: fake
            perp.cancel("ETH", 123)
        finally:
            perp.get_client = original_get_client

        args, _ = fake.exchange.cancel_args
        self.assertEqual(args, ("ETH", 123))


if __name__ == "__main__":
    unittest.main()
