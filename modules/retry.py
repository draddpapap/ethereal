import asyncio
import functools
from loguru import logger
from typing import Any, Callable
import time

class CustomError(Exception):
    """Пользовательская ошибка"""
    pass

class DataBaseError(CustomError):
    """Ошибка БД"""
    pass

class APIError(CustomError):
    """Ошибка API"""
    pass

def async_retry(max_retries: int = 3, delay: float = 2.0):
    """Декоратор для асинхронных функций с повторами"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (attempt + 1)
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} | "
                            f"Waiting {wait_time}s | Error: {str(e)[:100]}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Failed after {max_retries} retries: {e}")
            raise last_exception
        return wrapper
    return decorator

def sync_retry(max_retries: int = 3, delay: float = 2.0):
    """Декоратор для синхронных функций с повторами"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (attempt + 1)
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} | "
                            f"Waiting {wait_time}s | Error: {str(e)[:100]}"
                        )
                        time.sleep(wait_time)
            raise last_exception
        return wrapper
    return decorator

async def async_sleep(seconds: float):
    """Асинхронная задержка"""
    await asyncio.sleep(seconds)
