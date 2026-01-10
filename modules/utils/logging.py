from loguru import logger
from typing import Optional
import requests
from datetime import datetime


class TgReport:
    """Отправка отчётов в Telegram"""

    def __init__(self):
        from settings import TG_BOT_TOKEN, TG_USER_ID
        self.bot_token = TG_BOT_TOKEN
        self.user_ids = TG_USER_ID or []

    async def send_log(self, logs: str):
        """Отправить логи в Telegram"""
        if not self.bot_token or not self.user_ids:
            return

        if logs == 'No actions':
            return

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            # Разбить большие сообщения
            max_length = 4000
            messages = [logs[i:i + max_length] for i in range(0, len(logs), max_length)]

            for message in messages:
                for user_id in self.user_ids:
                    payload = {
                        "chat_id": user_id,
                        "text": message,
                        "parse_mode": "HTML"
                    }
                    requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.warning(f"Failed to send Telegram message: {e}")


class WindowName:
    """Управление названием окна терминала"""

    def __init__(self, accs_amount: int = 0):
        self.accs_amount = accs_amount
        self.accs_done = 0
        self.modules_done = 0

    def add_acc(self):
        """Добавить выполненный аккаунт"""
        self.accs_done += 1
        self._update()

    def add_module(self):
        """Добавить выполненный модуль"""
        self.modules_done += 1
        self._update()

    def set_modules(self, modules_amount: int):
        """Установить количество модулей"""
        self.modules_amount = modules_amount
        self._update()

    def _update(self):
        """Обновить название окна"""
        try:
            title = f"Ethereal Bot | Accounts: {self.accs_done}/{self.accs_amount} | Modules: {self.modules_done}"

            import os
            if os.name == 'nt':  # Windows
                os.system(f'title {title}')
            else:  # Linux/Mac
                print(f'\033]0;{title}\007', end='', flush=True)
        except Exception:
            pass
