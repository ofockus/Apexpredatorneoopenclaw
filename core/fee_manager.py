"""
core/fee_manager.py
APEX PREDATOR NEO v666.1 – Dynamic Fee Manager

Busca taxas reais da Binance via API e verifica desconto BNB.
Atualiza a cada 60 segundos para capturar mudanças de VIP tier.
"""
from __future__ import annotations

import time
from typing import Tuple

from loguru import logger
from config.config import cfg
from core.binance_connector import connector


class FeeManager:
    def __init__(self) -> None:
        self._maker: float = cfg.MAKER_FEE
        self._taker: float = cfg.TAKER_FEE
        self._bnb_discount: bool = False
        self._last_refresh: float = 0.0

    async def initialize(self) -> None:
        """Busca taxas reais da API."""
        await self._refresh()

    async def _refresh(self) -> None:
        try:
            info = await connector._exchange.fetch_trading_fees()
            sample = next(iter(info.values()), {})
            self._maker = float(sample.get("maker", cfg.MAKER_FEE))
            self._taker = float(sample.get("taker", cfg.TAKER_FEE))
            # Check BNB balance for discount
            bnb_bal = await connector.get_balance("BNB")
            self._bnb_discount = bnb_bal > 0.01
            self._last_refresh = time.monotonic()
            logger.info(f"💰 Fees refreshed: maker={self._maker:.5f} taker={self._taker:.5f} BNB={self._bnb_discount}")
        except Exception as e:
            logger.warning(f"Fee refresh failed, using defaults: {e}")

    def get_fees(self) -> Tuple[float, float]:
        return (self._maker, self._taker)

    @property
    def bnb_discount_active(self) -> bool:
        return self._bnb_discount

    @property
    def total_3_legs(self) -> float:
        avg = (self._maker + self._taker) / 2
        return avg * 3


fee_manager = FeeManager()
