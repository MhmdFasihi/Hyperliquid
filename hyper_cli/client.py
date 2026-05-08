"""Initialize and provide Hyperliquid Exchange and Info clients."""

from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants
from hyperliquid.websocket_manager import WebsocketManager

from hyper_cli.config import Config, load_config


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
            self._info = Info(constants.MAINNET_API_URL, skip_ws=True)
        return self._info

    def info_for_dex(self, dex: str = "") -> Info:
        if not dex:
            return self.info
        if dex not in self._infos:
            self._infos[dex] = Info(constants.MAINNET_API_URL, skip_ws=True, perp_dexs=[dex])
        return self._infos[dex]

    @property
    def exchange(self) -> Exchange:
        if self._exchange is None:
            account = Account.from_key(self._config.secret_key)
            self._exchange = Exchange(
                account,
                constants.MAINNET_API_URL,
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
                constants.MAINNET_API_URL,
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
            self._main_wallet_exchange = Exchange(account, constants.MAINNET_API_URL)
        return self._main_wallet_exchange

    @property
    def address(self) -> str:
        return self._config.account_address


def get_client() -> HyperClient:
    """Create a client from the default config."""
    return HyperClient(load_config())


def get_info(perp_dexs: list[str] | None = None) -> Info:
    """Create a public Info client for read-only market data."""
    return Info(constants.MAINNET_API_URL, skip_ws=True, perp_dexs=perp_dexs)


def get_ws_info(perp_dexs: list[str] | None = None) -> Info:
    """Create a public Info client with WebSocket support enabled."""
    info = Info(constants.MAINNET_API_URL, skip_ws=True, perp_dexs=perp_dexs)
    info.ws_manager = WebsocketManager(info.base_url)
    info.ws_manager.start()
    return info
