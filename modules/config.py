from dataclasses import dataclass


@dataclass
class EtherealConfig:
    """Конфигурация для Ethereal API"""

    base_url: str = "https://api.ethereal.trade"
    rpc_url: str = "https://rpc.ethereal.io"
    timeout: int = 30
    max_retries: int = 3

    @classmethod
    def testnet(cls):
        """Конфигурация для testnet"""
        return cls(
            base_url="https://api.etherealtest.net",
            rpc_url="https://rpc.etherealtest.net"
        )


# Текущая конфигурация (по умолчанию mainnet)
ETHEREAL_CONFIG = EtherealConfig()
