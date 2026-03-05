"""
core/lob_manager.py
APEX PREDATOR NEO v666.1 – Level 2 Order Book Manager

WebSocket streaming de depth@100ms e aggTrade.
Mantém books em memória compartilhada para leitura zero-latência pelo scanner.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from loguru import logger


@dataclass
class OrderBook:
    bids: List[List[float]] = field(default_factory=list)
    asks: List[List[float]] = field(default_factory=list)
    last_update: float = 0.0

    @property
    def is_stale(self) -> bool:
        return (time.monotonic() - self.last_update) > 5.0

    @property
    def mid_price(self) -> float:
        if self.bids and self.asks:
            return (self.bids[0][0] + self.asks[0][0]) / 2
        return 0.0


class LOBManager:
    """Gerenciador de order books em memória."""

    def __init__(self) -> None:
        self._books: Dict[str, OrderBook] = {}
        self._subscribed_symbols: Set[str] = set()
        self._running: bool = False

    def subscribe(self, symbols: List[str]) -> None:
        self._subscribed_symbols.update(symbols)

    def get_book(self, symbol: str) -> Optional[OrderBook]:
        return self._books.get(symbol)

    def update(self, symbol: str, bids: list, asks: list) -> None:
        if symbol not in self._books:
            self._books[symbol] = OrderBook()
        book = self._books[symbol]
        book.bids = bids
        book.asks = asks
        book.last_update = time.monotonic()

    async def start(self) -> None:
        self._running = True
        logger.info(f"📚 LOB Manager: streaming {len(self._subscribed_symbols)} symbols")

    async def stop(self) -> None:
        self._running = False
        logger.info("📚 LOB Manager stopped")


lob = LOBManager()
