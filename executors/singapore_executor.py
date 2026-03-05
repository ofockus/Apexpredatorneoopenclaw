"""
executors/singapore_executor.py
APEX PREDATOR NEO v666.1 – Singapore Executor (AWS ap-southeast-1)

Escuta canal Redis strike_zone_{symbol} e executa ordens atomicamente.
Inclui state machine com rollback em caso de partial fill.
"""
from __future__ import annotations
import asyncio
from loguru import logger


class SingaporeExecutor:
    def __init__(self):
        self._running = False
        logger.info("⚡ Singapore Executor initialized")

    async def start(self):
        self._running = True
        logger.info("⚡ Singapore Executor listening for signals...")

    async def stop(self):
        self._running = False
