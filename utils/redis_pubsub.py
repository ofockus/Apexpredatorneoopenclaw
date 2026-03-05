"""
utils/redis_pubsub.py
APEX PREDATOR NEO v666.1 – Redis Pub/Sub Message Bus

Comunicação entre scanner, executores e risk engine via Redis.
Serialização com orjson + timestamps em nanosegundos.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, Optional

import orjson
import redis.asyncio as aioredis
from loguru import logger

from config.config import cfg


class RedisBus:
    def __init__(self) -> None:
        self._redis: Optional[aioredis.Redis] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None

    async def connect(self) -> None:
        self._redis = aioredis.Redis(
            host=cfg.REDIS_HOST,
            port=cfg.REDIS_PORT,
            db=cfg.REDIS_DB,
            password=cfg.REDIS_PASSWORD or None,
            decode_responses=False,
        )
        await self._redis.ping()
        logger.success(f"📡 Redis conectado: {cfg.REDIS_HOST}:{cfg.REDIS_PORT}")

    async def disconnect(self) -> None:
        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
        logger.info("📡 Redis desconectado")

    async def publish(self, channel: str, data: Dict) -> None:
        if not self._redis:
            return
        payload = orjson.dumps({**data, "_ts_ns": time.time_ns()})
        await self._redis.publish(channel, payload)

    async def set_state(self, key: str, data: Dict, ttl: int = 300) -> None:
        if not self._redis:
            return
        await self._redis.set(key, orjson.dumps(data), ex=ttl)

    async def get_state(self, key: str) -> Optional[Dict]:
        if not self._redis:
            return None
        raw = await self._redis.get(key)
        return orjson.loads(raw) if raw else None

    async def listen(self, channels: list = None, callback: Callable = None) -> None:
        if not self._redis:
            return
        self._pubsub = self._redis.pubsub()
        chs = channels or [cfg.CH_OPPORTUNITIES, cfg.CH_RISK]
        await self._pubsub.subscribe(*chs)
        logger.info(f"📡 Listening: {chs}")
        async for msg in self._pubsub.listen():
            if msg["type"] == "message":
                data = orjson.loads(msg["data"])
                if callback:
                    await callback(msg["channel"].decode(), data)


redis_bus = RedisBus()
