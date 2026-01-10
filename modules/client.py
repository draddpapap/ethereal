from decimal import Decimal
from loguru import logger
from modules.browser import Browser
from modules.database import DataBase
from modules.retry import async_retry, CustomError
from typing import Dict, Optional, List
import asyncio
from random import choice, uniform, shuffle, randint
from settings import (
    SLEEP_BETWEEN_CLOSE_ORDERS,
    SLEEP_BETWEEN_OPEN_ORDERS,
    SLEEP_AFTER_FUTURE,
    STOP_LOSS_SETTING,
    TOKENS_TO_TRADE,
    FUTURES_LIMITS,
    FUTURE_ACTIONS,
    PAIR_SETTINGS,
    TRADE_AMOUNTS,
    CANCEL_ORDERS,
    RETRY,
)
from time import time


class EtherealClient:
    """Торговый клиент для одного аккаунта"""

    switch_params: Dict = {
        "BUY": "SELL",
        "SELL": "BUY",
    }

    actions_name: Dict = {
        "BUY": "Long",
        "SELL": "Short",
    }

    switch_actions: Dict = {
        "Long": "BUY",
        "Short": "SELL",
    }

    TOKENS_DATA: Dict = {}

    def __init__(
            self,
            browser: Browser,
            apikey: str,
            encoded_apikey: str,
            address: str,
            label: str,
            proxy: Optional[str],
            db: DataBase,
            group_data: Optional[Dict] = None
    ):
        self.browser = browser
        self.apikey = apikey
        self.encoded_apikey = encoded_apikey
        self.address = address
        self.label = label
        self.db = db

        if group_data:
            self.group_number = group_data["group_number"]
            self.encoded_apikey = group_data["group_index"]
            self.prefix = f"[<i>{self.label}</i>] "
        else:
            self.group_number = None
            self.prefix = f"[{self.label}] "


class PairAccounts:
    """Класс для работы с парами аккаунтов"""

    def __init__(self, accounts: List[EtherealClient], group_data: Dict):
        self.accounts = accounts
        self.group_data = group_data

    async def run(self, mode):
        # Заглушка для PairAccounts
        logger.info(f"Running PairAccounts for mode {mode}")
        return "completed"
