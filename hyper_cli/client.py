"""Initialize and provide Hyperliquid Exchange and Info clients."""

import requests

from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.websocket_manager import WebsocketManager

from hyper_cli.config import Config, load_config, public_api_url


class HyperClient:
    """Lazy-initialized wrapper around Exchange and Info."""

    def __init__(self, config: Config):
        self._config = config
        self._exchange: Exchange | None = None
        self._main_wallet_exchange: Exchange | None = None
        self._info: Info | None = None
        self._infos: dict[str, Info] = {}
        self._exchanges: dict[str, Exchange] = {}

    @property
    def info(self) -> Info:
        if self._info is None:
            self._info = _create_info(self._config.api_url, skip_ws=True)
        return self._info

    def info_for_dex(self, dex: str = "") -> Info:
        if not dex:
            return self.info
        if dex not in self._infos:
            self._infos[dex] = _create_info(self._config.api_url, skip_ws=True, perp_dexs=[dex])
        return self._infos[dex]

    @property
    def exchange(self) -> Exchange:
        if self._exchange is None:
            account = Account.from_key(self._config.secret_key)
            self._exchange = Exchange(
                account,
                self._config.api_url,
                account_address=self._config.account_address,
            )
        return self._exchange

    def exchange_for_dex(self, dex: str = "") -> Exchange:
        if not dex:
            return self.exchange
        if dex not in self._exchanges:
            account = Account.from_key(self._config.secret_key)
            self._exchanges[dex] = Exchange(
                account,
                self._config.api_url,
                account_address=self._config.account_address,
                perp_dexs=[dex],
            )
        return self._exchanges[dex]

    @property
    def main_wallet_exchange(self) -> Exchange:
        """Exchange client signed by the main wallet for user-signed actions."""
        if not self._config.main_wallet_secret_key:
            raise RuntimeError(
                "main_wallet_secret_key is required for user-signed account actions. "
                "Do not use an API agent key for user-signed account actions."
            )
        if self._main_wallet_exchange is None:
            account = Account.from_key(self._config.main_wallet_secret_key)
            if account.address.lower() != self._config.account_address.lower():
                raise RuntimeError("main_wallet_secret_key does not match account_address.")
            self._main_wallet_exchange = Exchange(account, self._config.api_url)
        return self._main_wallet_exchange

    @property
    def address(self) -> str:
        return self._config.account_address


def get_client() -> HyperClient:
    """Create a client from the default config."""
    return HyperClient(load_config())


def get_info(perp_dexs: list[str] | None = None) -> Info:
    """Create a public Info client for read-only market data."""
    return _create_info(public_api_url(), skip_ws=True, perp_dexs=perp_dexs)


def get_ws_info(perp_dexs: list[str] | None = None) -> Info:
    """Create a public Info client with WebSocket support enabled."""
    info = _create_info(public_api_url(), skip_ws=True, perp_dexs=perp_dexs)
    info.ws_manager = WebsocketManager(info.base_url)
    info.ws_manager.start()
    return info


def _create_info(base_url: str, *, skip_ws: bool, perp_dexs: list[str] | None = None) -> Info:
    spot_meta = _sanitize_spot_meta(_load_spot_meta(base_url))
    return Info(base_url, skip_ws=skip_ws, spot_meta=spot_meta, perp_dexs=perp_dexs)


def _load_spot_meta(base_url: str) -> dict:
    response = requests.post(f"{base_url}/info", json={"type": "spotMeta"}, timeout=10)
    response.raise_for_status()
    return response.json()


def _sanitize_spot_meta(spot_meta: dict) -> dict:
    tokens = spot_meta.get("tokens")
    universe = spot_meta.get("universe")
    if not isinstance(tokens, list) or not isinstance(universe, list):
        return spot_meta

    token_count = len(tokens)
    filtered = []
    for asset in universe:
        token_indexes = asset.get("tokens") if isinstance(asset, dict) else None
        if not isinstance(token_indexes, list):
            continue
        if all(isinstance(idx, int) and 0 <= idx < token_count for idx in token_indexes):
            filtered.append(asset)

    if len(filtered) == len(universe):
        return spot_meta

    sanitized = dict(spot_meta)
    sanitized["universe"] = filtered
    return sanitized
