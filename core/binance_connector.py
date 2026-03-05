"""
core/binance_connector.py
APEX PREDATOR NEO v666.1 – Conector Binance unificado (REST + cache agressivo).

Responsabilidades:
 - Conexão ccxt async com modo testnet/live automático
 - Cache de tickers (150ms) e orderbooks (15ms) para evitar rate limit
 - Ordens market e limit IOC para execução de baixa latência
 - Precisão automática (amount_to_precision / price_to_precision)
 - Simple Earn API para Auto-Earn Hook (busca melhor APR + inscrição)
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple

import ccxt.async_support as ccxt
from loguru import logger

from config.config import cfg


class BinanceConnector:
    """Conector unificado Binance Spot com cache agressivo."""

    def __init__(self) -> None:
        self._exchange: Optional[ccxt.binance] = None
        self._markets: Dict[str, Any] = {}
        self._symbols: List[str] = []
        self._ticker_cache: Dict[str, Dict] = {}
        self._ticker_ts: float = 0.0
        self._ob_cache: Dict[str, Dict] = {}
        self._ob_ts: Dict[str, float] = {}

    async def connect(self) -> None:
        """Inicializa exchange ccxt com sandbox ou live."""
        opts = {
            "defaultType": "spot",
            "adjustForTimeDifference": True,
            "recvWindow": 5000,
            "enableRateLimit": True,
            "rateLimit": 50,
        }
        if cfg.TESTNET:
            opts["sandboxMode"] = True

        self._exchange = ccxt.binance({
            "apiKey": cfg.api_key,
            "secret": cfg.api_secret,
            "options": opts,
            "timeout": 10000,
        })
        if cfg.TESTNET:
            self._exchange.set_sandbox_mode(True)

        self._markets = await self._exchange.load_markets(reload=True)
        self._symbols = [
            s for s, m in self._markets.items()
            if m.get("active") and m.get("spot")
        ]
        modo = "🟢 TESTNET" if cfg.TESTNET else "🔴 PRODUÇÃO LIVE"
        logger.success(f"✅ Binance [{modo}] — {len(self._symbols)} pares ativos")

    async def disconnect(self) -> None:
        if self._exchange:
            await self._exchange.close()
            logger.info("🔌 Binance desconectada")

    @property
    def markets(self) -> Dict[str, Any]:
        return self._markets

    @property
    def symbols(self) -> List[str]:
        return self._symbols

    def symbol_exists(self, symbol: str) -> bool:
        m = self._markets.get(symbol)
        return m is not None and m.get("active", False)

    def get_market(self, symbol: str) -> Optional[Dict]:
        return self._markets.get(symbol)

    async def fetch_all_tickers(self) -> Dict[str, Dict]:
        """Busca todos os tickers em uma única chamada REST (~200ms).
        Cache interno de 150ms para evitar rate limit."""
        now = time.monotonic()
        if now - self._ticker_ts < 0.150 and self._ticker_cache:
            return self._ticker_cache
        tickers = await self._exchange.fetch_tickers()
        self._ticker_cache = tickers
        self._ticker_ts = now
        return tickers

    async def fetch_orderbook(self, symbol: str, limit: int = 10) -> Dict:
        """Orderbook com cache de 15ms por símbolo."""
        now = time.monotonic()
        ts = self._ob_ts.get(symbol, 0.0)
        if now - ts < 0.015 and symbol in self._ob_cache:
            return self._ob_cache[symbol]
        ob = await self._exchange.fetch_order_book(symbol, limit)
        self._ob_cache[symbol] = ob
        self._ob_ts[symbol] = now
        return ob

    async def get_balance(self, asset: str = "USDT") -> float:
        bal = await self._exchange.fetch_balance()
        return float(bal.get("free", {}).get(asset, 0.0))

    async def market_buy(self, symbol: str, quote_amount: float) -> Dict:
        """Market buy com quoteOrderQty."""
        return await self._exchange.create_order(
            symbol, "market", "buy", None,
            params={"quoteOrderQty": self._exchange.cost_to_precision(symbol, quote_amount)},
        )

    async def market_sell(self, symbol: str, base_amount: float) -> Dict:
        """Market sell com quantidade de base asset."""
        amount = self._exchange.amount_to_precision(symbol, base_amount)
        return await self._exchange.create_order(symbol, "market", "sell", float(amount))

    async def simple_earn_subscribe(self, asset: str, amount: float) -> Optional[Dict]:
        """Inscreve no Simple Earn via API Binance (melhor APR flexível)."""
        try:
            products = await self._exchange.sapi_get_simple_earn_flexible_list(
                params={"asset": asset, "size": 10}
            )
            rows = products.get("rows", [])
            if not rows:
                return None
            best = max(rows, key=lambda r: float(r.get("latestAnnualPercentageRate", 0)))
            product_id = best["productId"]
            result = await self._exchange.sapi_post_simple_earn_flexible_subscribe(
                params={"productId": product_id, "amount": str(amount)}
            )
            logger.success(f"💰 Earn: {amount} {asset} → {best.get('asset')} APR={best.get('latestAnnualPercentageRate')}%")
            return result
        except Exception as e:
            logger.warning(f"Simple Earn falhou: {e}")
            return None


# Singleton global
connector = BinanceConnector()
