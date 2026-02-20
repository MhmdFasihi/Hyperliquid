"""Initialize and provide Hyperliquid Exchange and Info clients."""

from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

from hyper_cli.config import Config, load_config


class HyperClient:
    """Lazy-initialized wrapper around Exchange and Info."""

    def __init__(self, config: Config):
        self._config = config
        self._exchange: Exchange | None = None
        self._info: Info | None = None

    @property
    def info(self) -> Info:
        if self._info is None:
            self._info = Info(constants.MAINNET_API_URL, skip_ws=True)
        return self._info

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

    @property
    def address(self) -> str:
        return self._config.account_address


def get_client() -> HyperClient:
    """Create a client from the default config."""
    return HyperClient(load_config())
