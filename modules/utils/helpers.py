import asyncio
import time
from decimal import Decimal
from typing import Tuple, Optional


def round_cut(number: Decimal, decimals: int) -> Decimal:
    """Обрезать число до N знаков после запятой"""
    if decimals == 0:
        return Decimal(int(number))

    multiplier = Decimal(10) ** decimals
    return Decimal(int(number * multiplier)) / multiplier


async def async_sleep(seconds: float):
    """Асинхронная задержка"""
    if seconds > 0:
        await asyncio.sleep(seconds)


def sleeping(seconds: float):
    """Синхронная задержка"""
    if seconds > 0:
        time.sleep(seconds)


def make_border(text: str, width: int = 50, char: str = "=") -> str:
    """Создать рамку вокруг текста"""
    border = char * width
    return f"\n\n{border}\n{text}\n{border}\n"


def get_address(private_key: str) -> str:
    """Получить адрес кошелька из приватного ключа"""
    try:
        # Если это просто hex ключ, вернём его часть как адрес
        if len(private_key) == 64 or len(private_key) == 66:
            return "0x" + private_key[:40] if private_key.startswith('0x') else private_key[:40]
        return private_key[:42]
    except Exception:
        return private_key[:42]


def calculate_setting_difference(
        amounts: list,
        percents: list
) -> Tuple[Decimal, Decimal]:
    """Рассчитать разницу из параметров"""
    from random import uniform

    percent = Decimal("1")
    amount = Decimal("0")

    if amounts != [0, 0]:
        amount = Decimal(str(uniform(*amounts)))
    else:
        random_percent = uniform(*percents)
        percent = Decimal("1") + Decimal(str(random_percent)) / 100

    return percent, amount


class MultiLock:
    """Множественный лок для нескольких адресов"""

    _locks = {}

    def __init__(self, addresses: list):
        self.addresses = addresses
        self.locks = [self._get_lock(addr) for addr in addresses]

    @classmethod
    def _get_lock(cls, address: str):
        """Получить или создать лок для адреса"""
        if address not in cls._locks:
            cls._locks[address] = asyncio.Lock()
        return cls._locks[address]

    async def __aenter__(self):
        """Вход в контекст"""
        for lock in self.locks:
            await lock.acquire()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекста"""
        for lock in self.locks:
            lock.release()
