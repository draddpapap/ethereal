from random import choice, randint, shuffle
from cryptography.fernet import Fernet, InvalidToken
from base64 import urlsafe_b64encode
from time import sleep, time
from os import path, mkdir
from loguru import logger
from hashlib import md5
import asyncio
import json
from modules.retry import DataBaseError
from settings import (
    SHUFFLE_WALLETS,
    PAIR_SETTINGS,
    TRADES_COUNT,
    RETRY,
)


class DataBase:
    """Управление базой данных с шифрованием"""

    STATUS_SMILES = {
        True: '✅ ',
        False: "❌ ",
        None: "",
        "WARNING": "⚠️ ",
    }

    lock = asyncio.Lock()

    def __init__(self):
        self.modules_db_name = 'databases/modules.json'
        self.report_db_name = 'databases/report.json'
        self.stats_db_name = 'databases/stats.json'
        self.personal_key = None

        # Создать папки если их нет
        if not path.isdir('databases'):
            mkdir('databases')

        # Создать БД если их нет
        for db_params in [
            {"name": self.modules_db_name, "value": "{}"},
            {"name": self.report_db_name, "value": "{}"},
            {"name": self.stats_db_name, "value": "{}"},
        ]:
            if not path.isfile(db_params["name"]):
                with open(db_params["name"], 'w') as f:
                    f.write(db_params["value"])

        amounts = self.get_amounts()
        if amounts.get("groups_amount"):
            logger.info(f'Loaded {amounts["groups_amount"]} groups\n')
        else:
            logger.info(f'Loaded {amounts["modules_amount"]} modules for {amounts["accs_amount"]} accounts\n')

    def set_password(self):
        """Установить пароль для шифрования"""
        if self.personal_key is not None:
            return

        logger.debug('Enter password to encrypt API keys (empty for default):')
        raw_password = input("")

        if not raw_password:
            raw_password = "@karamelniy dumb shit encrypting"
            logger.success('[+] Soft | You set empty password for Database\n')
        else:
            print('')
            sleep(0.2)

        password = md5(raw_password.encode()).hexdigest().encode()
        self.personal_key = Fernet(urlsafe_b64encode(password))

    def get_password(self):
        """Получить пароль для дешифровки"""
        if self.personal_key is not None:
            return

        with open(self.modules_db_name, encoding="utf-8") as f:
            modules_db = json.load(f)

        if not modules_db:
            return

        # Попробовать default пароль
        first_key = list(modules_db.keys())[0]
        try:
            temp_key = Fernet(
                urlsafe_b64encode(
                    md5("@karamelniy dumb shit encrypting".encode()).hexdigest().encode()
                )
            )
            self.decode_pk(pk=first_key, key=temp_key)
            self.personal_key = temp_key
            return
        except InvalidToken:
            pass

        # Попросить пароль у пользователя
        while True:
            try:
                logger.debug('Enter password to decrypt your API keys (empty for default):')
                raw_password = input("")
                password = md5(raw_password.encode()).hexdigest().encode()
                temp_key = Fernet(urlsafe_b64encode(password))
                self.decode_pk(pk=first_key, key=temp_key)
                self.personal_key = temp_key
                logger.success('[+] Soft | Access granted!\n')
                return
            except InvalidToken:
                logger.error('[-] Soft | Invalid password\n')

    def encode_pk(self, pk: str, key=None):
        """Зашифровать ключ"""
        if key is None:
            return self.personal_key.encrypt(pk.encode()).decode()
        return key.encrypt(pk.encode()).decode()

    def decode_pk(self, pk: str, key=None):
        """Расшифровать ключ"""
        if key is None:
            return self.personal_key.decrypt(pk).decode()
        return key.decrypt(pk).decode()

    def create_modules(self, mode: int):
        """Создать модули торговли"""

        def create_single_trades(apikeys, labels, proxies):
            return {
                self.encode_pk(apikey): {
                    "address": self.encode_pk(apikey.split(':')[0]),
                    "modules": [
                        {"module_name": "trade", "status": "to_run"}
                        for _ in range(randint(*TRADES_COUNT))
                    ],
                    "proxy": proxy,
                    "label": label,
                }
                for apikey, label, proxy in zip(apikeys, labels, proxies)
            }

        def create_pair_trades(apikeys, labels, proxies):
            min_pair_size = max(2, min(*PAIR_SETTINGS["pair_amount"]))
            if len(apikeys) < min_pair_size:
                raise DataBaseError(f'Not enough accounts, need at least {min_pair_size}')

            encoded_api_keys = [self.encode_pk(apikey) for apikey in apikeys]
            addresses = [self.encode_pk(apikey.split(':')[0]) for apikey in apikeys]

            all_modules = [
                {
                    'encoded_apikey': encoded_apikey,
                    "address": address,
                    'label': label,
                    'proxy': proxy,
                }
                for encoded_apikey, address, label, proxy in zip(
                    encoded_api_keys, addresses, labels, proxies
                )
                for _ in range(randint(*TRADES_COUNT))
            ]

            pairs_list = []
            while True:
                pair_size = max(2, randint(*PAIR_SETTINGS["pair_amount"]))
                unique_wallets_left = list({
                                               module["address"]: module for module in all_modules
                                           }.values())

                if len(unique_wallets_left) < min_pair_size:
                    break

                if len(unique_wallets_left) < pair_size:
                    pair_size = min_pair_size

                pairs_list.append([])
                for _ in range(pair_size):
                    random_wallet = unique_wallets_left.pop(
                        randint(0, len(unique_wallets_left) - 1)
                    )
                    all_modules.remove(random_wallet)
                    pairs_list[-1].append(random_wallet)

            return {
                f"{pair_index + 1}_{int(time())}": {
                    "group_number": pair_index + 1,
                    'modules': [{"module_name": "trade", "status": "to_run"}],
                    "wallets_data": pair
                }
                for pair_index, pair in enumerate(pairs_list)
            }

        self.set_password()

        with open('input_data/apikeys.txt') as f:
            raw_apikeys = f.read().splitlines()

        labels = []
        api_keys = []

        for key_index, raw_apikey in enumerate(raw_apikeys):
            if not raw_apikey or raw_apikey.startswith('#'):
                continue

            apikey_data = raw_apikey.split(':')

            if len(apikey_data) == 2:
                labels.append(f"Account {key_index + 1}")
                api_keys.append(raw_apikey)
            elif len(apikey_data) == 3:
                labels.append(apikey_data[0])
                api_keys.append(f"{apikey_data[1]}:{apikey_data[2]}")
            else:
                raise DataBaseError(f"Unexpected format: {raw_apikey}")

        with open('input_data/proxies.txt') as f:
            proxies = [p for p in f.read().splitlines() if p and not p.startswith('#')]

        if not proxies or proxies == ['http://login:password@ip:port']:
            logger.warning('No proxies configured')
            proxies = [None for _ in range(len(api_keys))]
        else:
            proxies = list(proxies * (len(api_keys) // len(proxies) + 1))[:len(api_keys)]

        with open(self.report_db_name, 'w') as f:
            f.write('{}')

        if mode == 102:
            new_modules = create_pair_trades(api_keys, labels, proxies)
        else:
            new_modules = create_single_trades(api_keys, labels, proxies)

        with open(self.modules_db_name, 'w', encoding="utf-8") as f:
            json.dump(new_modules, f)

        logger.opt(colors=True).critical(
            'Dont Forget To Remove API Keys from <white>apikeys.txt</white>!'
        )

        amounts = self.get_amounts()
        if mode == 102:
            logger.info(f'Created Database with {amounts["groups_amount"]} groups!\n')
        else:
            logger.info(
                f'Created Database for {amounts["accs_amount"]} accounts '
                f'with {amounts["modules_amount"]} modules!\n'
            )

    def get_amounts(self):
        """Получить количество модулей и аккаунтов"""
        with open(self.modules_db_name, encoding="utf-8") as f:
            modules_db = json.load(f)

        if not modules_db:
            return {"accs_amount": 0, "modules_amount": 0, "groups_amount": 0}

        first_val = list(modules_db.values())[0]
        is_group = "group_number" in first_val

        modules_len = sum([len(modules_db[acc].get("modules", [])) for acc in modules_db])

        return {
            "groups_amount" if is_group else "accs_amount": len(modules_db),
            "modules_amount": modules_len
        }

    def get_all_modules(self, unique_wallets: bool = False):
        """Получить все модули для выполнения"""
        self.get_password()

        with open(self.modules_db_name, encoding="utf-8") as f:
            modules_db = json.load(f)

        if not modules_db:
            return 'No more accounts left'

        is_group = "group_number" in list(modules_db.values())[0]
        if is_group:
            raise DataBaseError('Unexpected database type for this mode')

        all_modules = list(modules_db.values())
        return all_modules
