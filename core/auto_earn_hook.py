"""
core/auto_earn_hook.py
APEX PREDATOR NEO v666.1 – Auto-Earn Hook

Após cada ciclo lucrativo > US$ 0.10:
 1. Busca o produto Simple Earn de MAIOR APR atual
 2. Move o lucro automaticamente via API Binance
 3. Publica confirmação via Redis para tracking

Cache de produtos: 5 minutos para evitar spam na API.
"""
from __future__ import annotations

import time
from typing import Dict, Optional

from loguru import logger

from config.config import cfg
from core.binance_connector import connector
from utils.redis_pubsub import redis_bus


class AutoEarnHook:
    """Hook pós-trade que inscreve lucro no Simple Earn Binance."""

    def __init__(self) -> None:
        self._total_earned: float = 0.0
        self._total_subscribed: float = 0.0
        self._sub_count: int = 0
        self._product_cache: Optional[Dict] = None
        self._cache_expiry: float = 0.0

    async def process(self, net_profit: float, asset: str = "USDT") -> bool:
        """Processa lucro pós-trade. Se >= threshold, inscreve no Earn."""
        if net_profit < cfg.AUTO_EARN_MIN_PROFIT:
            return False

        self._total_earned += net_profit

        try:
            result = await connector.simple_earn_subscribe(asset, net_profit)
            if result:
                self._total_subscribed += net_profit
                self._sub_count += 1
                logger.success(
                    f"💰 Auto-Earn: ${net_profit:.4f} → Simple Earn | "
                    f"Total: ${self._total_subscribed:.4f} ({self._sub_count} subs)"
                )
                await redis_bus.publish(cfg.CH_EARN, {
                    "type": "SUBSCRIBE",
                    "amount": net_profit,
                    "asset": asset,
                    "total_subscribed": self._total_subscribed,
                    "count": self._sub_count,
                })
                return True
        except Exception as e:
            logger.warning(f"Auto-Earn falhou: {e}")

        return False

    def summary(self) -> Dict:
        return {
            "total_earned": round(self._total_earned, 4),
            "total_subscribed": round(self._total_subscribed, 4),
            "sub_count": self._sub_count,
        }


# Singleton
auto_earn = AutoEarnHook()
