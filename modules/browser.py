from decimal import Decimal
from loguru import logger
from modules.retry import async_retry, APIError
from typing import Dict, List, Optional
import aiohttp
import asyncio
from modules.config import ETHEREAL_CONFIG
import json


class Browser:
    """HTTP клиент для Ethereal REST API (без SDK)"""

    def __init__(
            self,
            private_key: str,
            label: str,
            proxy: Optional[str] = None,
            base_url: str = "https://api.ethereal.trade"
    ):
        self.private_key = private_key
        self.label = label
        self.proxy = self._format_proxy(proxy)
        self.base_url = base_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
        self.max_retries = 5

    @staticmethod
    def _format_proxy(proxy: Optional[str]) -> Optional[str]:
        """Форматировать прокси"""
        if not proxy or proxy in ['', ' ', '\n', 'http://log:pass@ip:port']:
            return None

        if proxy.startswith(('http://', 'https://')):
            return proxy

        return f"http://{proxy}"

    async def initialize(self):
        """Инициализировать сессию"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }

            connector = aiohttp.TCPConnector(ssl=False, limit_per_host=5)
            self.session = aiohttp.ClientSession(
                headers=headers,
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30)
            )

            logger.opt(colors=True).debug(
                f'[•] <white>{self.label}</white> | Initialized Ethereal HTTP client'
            )
        except Exception as e:
            raise APIError(f"Failed to initialize HTTP client: {e}")

    async def close_sessions(self):
        """Закрыть сессию"""
        if self.session:
            try:
                await self.session.close()
                await asyncio.sleep(0.25)
            except Exception as e:
                logger.warning(f"Error closing session: {e}")

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Генерический метод для HTTP запросов"""
        if not self.session:
            await self.initialize()

        url = f"{self.base_url}{endpoint}"

        try:
            async with self.session.request(
                    method,
                    url,
                    proxy=self.proxy,
                    **kwargs
            ) as response:
                text = await response.text()

                try:
                    data = json.loads(text) if text else {}
                except json.JSONDecodeError:
                    data = {}

                if response.status >= 400:
                    error_msg = data.get('message') or data.get('error') or text[:200]
                    raise APIError(f"API Error {response.status}: {error_msg}")

                return data
        except asyncio.TimeoutError:
            raise APIError(f"Request timeout to {url}")
        except aiohttp.ClientError as e:
            raise APIError(f"HTTP Client Error: {e}")
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Request failed: {e}")

    @async_retry(max_retries=3)
    async def get_products(self) -> List[Dict]:
        """Получить список доступных продуктов"""
        try:
            data = await self._request("GET", "/products")
            products = data if isinstance(data, list) else data.get("products", [])
            return products
        except Exception as e:
            raise APIError(f"Failed to get products: {e}")

    @async_retry(max_retries=3)
    async def get_balance(self) -> Decimal:
        """Получить баланс USDE"""
        try:
            data = await self._request("GET", "/accounts")

            if isinstance(data, dict):
                balance = data.get("balance") or data.get("free_balance") or 0
                return Decimal(str(balance))

            return Decimal("0")
        except Exception as e:
            logger.warning(f"Failed to get balance: {e}")
            return Decimal("0")

    @async_retry(max_retries=3)
    async def get_price(self, ticker: str) -> Decimal:
        """Получить текущую цену токена"""
        try:
            data = await self._request("GET", f"/markets/{ticker}")

            if isinstance(data, dict):
                price = (data.get("price") or
                         data.get("mark_price") or
                         data.get("lastPrice") or
                         data.get("indexPrice"))
                if price:
                    return Decimal(str(price))

            raise APIError(f"No price data for {ticker}")
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Failed to get price for {ticker}: {e}")

    @async_retry(max_retries=3)
    async def get_order_book(self, ticker: str) -> Dict[str, Decimal]:
        """Получить стакан заявок"""
        try:
            data = await self._request("GET", f"/orderbooks/{ticker}?limit=5")

            if isinstance(data, dict):
                bids = data.get("bids", [])
                asks = data.get("asks", [])

                bid_price = Decimal(str(bids[0][0])) if bids else Decimal("0")
                ask_price = Decimal(str(asks[0][0])) if asks else Decimal("0")

                return {
                    "BUY": bid_price,
                    "SELL": ask_price
                }

            raise APIError(f"Invalid order book data for {ticker}")
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Failed to get order book for {ticker}: {e}")

    @async_retry(max_retries=3)
    async def create_order(self, order_data: Dict) -> Dict:
        """Создать ордер"""
        try:
            payload = {
                "order_type": order_data.get("type", "LIMIT"),
                "quantity": str(order_data.get("quantity", 0)),
                "side": "buy" if order_data.get("side") == 0 else "sell",
                "ticker": order_data.get("ticker"),
            }

            if order_data.get("type") == "LIMIT":
                payload["price"] = str(order_data.get("price", 0))

            data = await self._request("POST", "/orders", json=payload)

            return {
                "orderId": data.get("id") or data.get("order_id"),
                "status": "PENDING",
                "symbol": order_data.get("ticker"),
                "side": "BUY" if order_data.get("side") == 0 else "SELL",
                "quantity": float(order_data.get("quantity")),
                "price": float(order_data.get("price", 0)),
                "executedQty": 0.0,
                "avgPrice": float(order_data.get("price", 0)),
                "cumQuote": 0.0,
            }
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Failed to create order: {e}")

    @async_retry(max_retries=3)
    async def cancel_order(self, order_id: str, ticker: str = "") -> bool:
        """Отменить ордер"""
        try:
            data = await self._request("DELETE", f"/orders/{order_id}")

            if data.get("status") == "canceled" or data.get("success"):
                return True

            raise APIError(f"Failed to cancel order {order_id}")
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Failed to cancel order {order_id}: {e}")

    @async_retry(max_retries=3)
    async def get_order_status(self, order_id: str, ticker: str = "") -> Dict:
        """Получить статус ордера"""
        try:
            data = await self._request("GET", f"/orders/{order_id}")

            executed_qty = float(data.get("filled_quantity") or 0)
            price = float(data.get("price") or 0)

            return {
                "orderId": data.get("id") or order_id,
                "status": data.get("status") or "PENDING",
                "executedQty": executed_qty,
                "avgPrice": price,
                "cumQuote": executed_qty * price,
            }
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Failed to get order status: {e}")

    @async_retry(max_retries=3)
    async def get_positions(self) -> List[Dict]:
        """Получить открытые позиции"""
        try:
            data = await self._request("GET", "/positions")

            positions = data if isinstance(data, list) else data.get("positions", [])

            result = []
            for pos in positions:
                size = float(pos.get("size") or 0)
                if size != 0:
                    result.append({
                        "symbol": pos.get("product_id") or pos.get("ticker"),
                        "positionAmt": size,
                        "entryPrice": float(pos.get("entry_price") or 0),
                    })

            return result
        except Exception as e:
            logger.warning(f"Failed to get positions: {e}")
            return []

    @async_retry(max_retries=3)
    async def get_open_orders(self) -> List[Dict]:
        """Получить открытые ордеры"""
        try:
            data = await self._request("GET", "/orders?status=pending")

            orders = data if isinstance(data, list) else data.get("orders", [])

            result = []
            for order in orders:
                result.append({
                    "orderId": order.get("id") or order.get("order_id"),
                    "symbol": order.get("ticker") or order.get("product_id"),
                    "status": order.get("status"),
                    "quantity": float(order.get("quantity") or 0),
                    "price": float(order.get("price") or 0),
                })

            return result
        except Exception as e:
            logger.warning(f"Failed to get open orders: {e}")
            return []

    @async_retry(max_retries=3)
    async def close_all_orders(self, ticker: str) -> bool:
        """Закрыть все ордеры по символу"""
        try:
            orders = await self.get_open_orders()
            order_ids = [o["orderId"] for o in orders if ticker in o.get("symbol", "")]

            if order_ids:
                for order_id in order_ids:
                    try:
                        await self.cancel_order(order_id, ticker)
                    except Exception as e:
                        logger.warning(f"Failed to cancel order {order_id}: {e}")

            return True
        except Exception as e:
            raise APIError(f"Failed to close all orders for {ticker}: {e}")
