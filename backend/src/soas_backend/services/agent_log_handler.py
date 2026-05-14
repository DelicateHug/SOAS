"""Python logging.Handler that batches log records into the agent_logs table.

Attach once at process startup; every record on the root logger (or any
logger that propagates to root) is buffered in memory and flushed in
batches of up to BATCH_SIZE records or every FLUSH_INTERVAL_S seconds,
whichever comes first.

Best-effort: a flush failure is silently retried on the next tick.
Never blocks the caller.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

from soas_backend.database import async_session
from soas_backend.models.agent_log import AgentLog

BATCH_SIZE = 100
FLUSH_INTERVAL_S = 10.0
MAX_QUEUE = 5000


class AgentLogHandler(logging.Handler):
    def __init__(self, agenttype_id: str, version: str) -> None:
        super().__init__()
        self.agenttype_id = agenttype_id
        self.version = version
        self._queue: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._stop = False
        self._loop_task: asyncio.Task[None] | None = None

    # Loggers whose INFO output is too chatty to mirror into agent_logs.
    # SQL traces, HTTP access logs, websocket churn — they belong in stdout
    # but flood the per-agent view.
    _SILENCE_PREFIXES = (
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "uvicorn.access",
        "fastapi.access",
        "watchfiles",
        "asyncio",
        "soas_backend.services.agent_log_handler",
    )

    def emit(self, record: logging.LogRecord) -> None:
        # Drop debug noise; keep info and up.
        if record.levelno < logging.INFO:
            return
        # Filter chatty loggers — they're still in stdout for direct tailing.
        for p in self._SILENCE_PREFIXES:
            if record.name.startswith(p):
                return
        try:
            level = record.levelname.lower()
            if level == "warning":
                level = "warn"
            elif level == "critical":
                level = "fatal"
            msg = self.format(record)
            entry = {
                "level": level[:16],
                "message": msg[:16000],
                "context": {
                    "logger": record.name,
                    "func": record.funcName,
                    "line": record.lineno,
                },
                "version": self.version,
                "occurred_at": datetime.fromtimestamp(record.created, tz=timezone.utc),
            }
            with self._lock:
                if len(self._queue) < MAX_QUEUE:
                    self._queue.append(entry)
        except Exception:
            pass  # never raise from a logging handler

    async def start(self) -> None:
        """Begin the periodic flusher. Call once at app startup."""
        if self._loop_task is not None:
            return
        self._loop_task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop = True
        if self._loop_task:
            try:
                await self._loop_task
            except Exception:
                pass

    async def _run(self) -> None:
        while not self._stop:
            await asyncio.sleep(FLUSH_INTERVAL_S)
            await self._flush()
        await self._flush()

    async def _flush(self) -> None:
        with self._lock:
            if not self._queue:
                return
            batch = self._queue[:BATCH_SIZE]
            del self._queue[: len(batch)]
        try:
            async with async_session() as db:
                for entry in batch:
                    db.add(
                        AgentLog(
                            agenttype_id=self.agenttype_id,
                            level=entry["level"],
                            message=entry["message"],
                            context=entry["context"],
                            version=entry["version"],
                            occurred_at=entry["occurred_at"],
                        )
                    )
                await db.commit()
        except Exception:
            # Push the batch back at the front for retry on the next tick.
            with self._lock:
                self._queue[:0] = batch
