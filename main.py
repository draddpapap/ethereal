from os import name as os_name
from random import randint
from loguru import logger
from time import sleep
import asyncio
from modules.retry import DataBaseError
from modules.utils import choose_mode, async_sleep
from modules import *
import settings


def initialize_account(module_data: dict, group_data: dict = None):
    """Инициализировать аккаунт"""
    browser = Browser(
        private_key=module_data["apikey"],
        label=module_data["label"],
        proxy=module_data.get("proxy"),
        base_url=settings.ETHEREAL_API_URL
    )

    ethereal_client = EtherealClient(
        browser=browser,
        apikey=module_data["apikey"],
        encoded_apikey=module_data["encoded_apikey"],
        address=module_data["address"],
        label=module_data["label"],
        proxy=module_data.get("proxy"),
        db=db,
        group_data=group_data,
    )

    return ethereal_client


# Global address locks
address_locks = {}


async def run_modules(mode: int, module_data: dict, sem: asyncio.Semaphore):
    """Запустить модуль торговли"""
    address = module_data["address"]

    # Создать лок для адреса если его нет
    if address not in address_locks:
        address_locks[address] = asyncio.Lock()

    async with address_locks[address]:
        async with sem:
            ethereal_client = None
            try:
                ethereal_client = initialize_account(module_data)
                module_data["module_info"]["status"] = await ethereal_client.run_mode(mode=mode)
            except Exception as err:
                if ethereal_client:
                    logger.error(f'[-] {ethereal_client.label} | Account Error: {err}')
                    await db.append_report(
                        key=ethereal_client.encoded_apikey,
                        text=str(err),
                        success=False
                    )
                else:
                    logger.error(f'[-] {module_data["label"]} | Global error: {err}')
            finally:
                if ethereal_client:
                    await ethereal_client.browser.close_sessions()

                if isinstance(module_data, dict):
                    if mode in [1, 2]:
                        await db.remove_module(module_data=module_data)
                    else:
                        await db.remove_account(module_data=module_data)

                    reports = await db.get_account_reports(
                        key=ethereal_client.encoded_apikey,
                        label=ethereal_client.label,
                        address=ethereal_client.address,
                        last_module=True,
                        mode=mode,
                    )

                    await TgReport().send_log(logs=reports)

                    if module_data["module_info"]["status"] is True:
                        await async_sleep(randint(*settings.SLEEP_AFTER_ACC))
                    else:
                        await async_sleep(10)


async def run_pair(mode: int, group_data: dict, sem: asyncio.Semaphore):
    """Запустить парную торговлю"""
    addresses = [w["address"] for w in group_data["wallets_data"]]

    # Создать локи для всех адресов в группе
    for addr in addresses:
        if addr not in address_locks:
            address_locks[addr] = asyncio.Lock()

    # Получить все локи для этой группы
    group_locks = [address_locks[addr] for addr in addresses]

    async with sem:
        ethereal_clients = []
        try:
            # Захватить все локи
            for lock in group_locks:
                await lock.acquire()

            ethereal_clients = [
                initialize_account(wallet_data, group_data=group_data)
                for wallet_data in group_data["wallets_data"]
            ]

            group_data["module_info"]["status"] = await PairAccounts(
                accounts=ethereal_clients,
                group_data=group_data
            ).run(mode=mode)
        except Exception as err:
            logger.error(f'[-] Group {group_data["group_number"]} | Error: {err}')
            await db.append_report(
                key=group_data.get("group_index"),
                text=str(err),
                success=False
            )
        finally:
            # Отпустить все локи
            for lock in group_locks:
                lock.release()

            if ethereal_clients:
                for ethereal_client in ethereal_clients:
                    await ethereal_client.browser.close_sessions()

            await db.remove_group(group_data=group_data)

            reports = await db.get_account_reports(
                key=group_data.get("group_index"),
                label=f"Group {group_data['group_number']}",
                address=None,
                last_module=False,
                mode=mode,
            )

            await TgReport().send_log(logs=reports)

            if group_data["module_info"]["status"] is True:
                to_sleep = randint(*settings.SLEEP_AFTER_ACC)
                logger.opt(colors=True).debug(
                    f'[•] <white>Group {group_data["group_number"]}</white> | Sleep {to_sleep}s'
                )
                await async_sleep(to_sleep)
            else:
                await async_sleep(10)


async def runner(mode: int):
    """Основной runner"""
    sem = asyncio.Semaphore(settings.THREADS)

    if mode == 3:
        # Парная торговля
        all_groups = db.get_all_groups()
        if all_groups != 'No more accounts left':
            await asyncio.gather(*[
                run_pair(group_data=group_data, mode=mode, sem=sem)
                for group_data in all_groups
            ])
    else:
        # Одиночная торговля
        all_modules = db.get_all_modules(unique_wallets=mode in [4, 5])
        if all_modules != 'No more accounts left':
            await asyncio.gather(*[
                run_modules(module_data=module_data, mode=mode, sem=sem)
                for module_data in all_modules
            ])

    logger.success('✓ All accounts done.')
    return 'Ended'


if __name__ == '__main__':
    if os_name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        db = DataBase()

        while True:
            mode = choose_mode()

            if mode.type == "database":
                db.create_modules(mode=mode.soft_id)
            elif mode.type == "module":
                if asyncio.run(runner(mode=mode.soft_id)) == 'Ended':
                    break

            print('')
            sleep(0.1)

        input('\n > Exit\n')
    except DataBaseError as e:
        logger.error(f'[-] Database | {e}')
    except KeyboardInterrupt:
        logger.info('[•] Interrupted by user')
    finally:
        logger.info('[•] Soft | Closed')
