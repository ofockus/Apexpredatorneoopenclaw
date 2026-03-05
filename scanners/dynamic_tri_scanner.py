"""
scanners/dynamic_tri_scanner.py
APEX PREDATOR NEO v666.1 – Dynamic Triangle Scanner

Descobre automaticamente todos os caminhos triangulares válidos
e avalia em tempo real usando preços do LOB + ConfluenceEngine.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from loguru import logger

from config.config import cfg
from core.binance_connector import connector
from core.confluence_engine import confluence
from core.fee_manager import fee_manager
from core.robin_hood_risk import robin_hood
from utils.redis_pubsub import redis_bus


class DynamicTriScanner:
    def __init__(self) -> None:
        self._triangles: List[Dict] = []
        self._running: bool = False
        self._scan_count: int = 0

    async def discover(self) -> int:
        """Descobre todos os caminhos triangulares válidos."""
        markets = connector.markets
        symbols = set(connector.symbols)
        found = []

        for base in cfg.BASE_ASSETS:
            for quote1 in cfg.QUOTE_ASSETS:
                for quote2 in cfg.QUOTE_ASSETS:
                    if quote1 == quote2:
                        continue
                    leg1 = f"{base}/{quote1}"
                    leg2 = f"{base}/{quote2}"
                    leg3 = f"{quote2}/{quote1}"
                    if leg1 in symbols and leg2 in symbols and leg3 in symbols:
                        found.append({
                            "id": f"{quote1}>{base}>{quote2}>{quote1}",
                            "legs": [
                                {"symbol": leg1, "side": "buy"},
                                {"symbol": leg2, "side": "sell"},
                                {"symbol": leg3, "side": "sell"},
                            ],
                            "base": base,
                            "quote1": quote1,
                            "quote2": quote2,
                        })

        self._triangles = found
        logger.success(f"🔺 Descobertos {len(found)} caminhos triangulares")
        return len(found)

    async def run(self) -> None:
        """Loop principal de escaneamento."""
        self._running = True
        interval = cfg.SCAN_INTERVAL_MS / 1000.0

        while self._running:
            t0 = time.monotonic()
            try:
                tickers = await connector.fetch_all_tickers()
                opportunities = []

                for tri in self._triangles:
                    spread = self._calc_spread(tri, tickers)
                    if spread is None:
                        continue

                    net = spread - fee_manager.total_3_legs * 100
                    if net > cfg.MIN_PROFIT_PCT:
                        # Run confluence
                        obs = {}
                        for leg in tri["legs"]:
                            try:
                                obs[leg["symbol"]] = await connector.fetch_orderbook(leg["symbol"])
                            except Exception:
                                pass

                        result = confluence.analyze(tri, obs, tickers)
                        if result.is_valid:
                            opp = {
                                "triangle": tri,
                                "spread_pct": spread,
                                "net_pct": net,
                                "confluence": result.score,
                                "ts": time.time_ns(),
                            }
                            opportunities.append(opp)

                # Publish best opportunity
                if opportunities and robin_hood.is_allowed:
                    best = max(opportunities, key=lambda o: o["net_pct"])
                    await redis_bus.publish(cfg.CH_OPPORTUNITIES, best)

                self._scan_count += 1
                elapsed = (time.monotonic() - t0) * 1000

                if self._scan_count % 100 == 0:
                    logger.info(
                        f"🔍 Scan #{self._scan_count} | {elapsed:.1f}ms | "
                        f"{len(opportunities)} opps | {len(self._triangles)} paths"
                    )

            except Exception as e:
                logger.error(f"Scan error: {e}")

            sleep_time = max(0, interval - (time.monotonic() - t0))
            await asyncio.sleep(sleep_time)

    def _calc_spread(self, tri: Dict, tickers: Dict) -> Optional[float]:
        """Calcula spread do triângulo usando preços de ticker."""
        try:
            legs = tri["legs"]
            result = 1.0
            for leg in legs:
                tk = tickers.get(leg["symbol"], {})
                if leg["side"] == "buy":
                    ask = tk.get("ask")
                    if not ask or ask <= 0:
                        return None
                    result /= ask
                else:
                    bid = tk.get("bid")
                    if not bid or bid <= 0:
                        return None
                    result *= bid
            return (result - 1.0) * 100
        except Exception:
            return None

    def stop(self) -> None:
        self._running = False


scanner = DynamicTriScanner()
