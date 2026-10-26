"""Concurrent native calls with complete draining before errors or shutdown."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from .core import InfrastructureError


class RequestPool:
    def __init__(self, worker):
        self.worker = worker
        self.active = {}
        self.executors = []
        self.width = 0

    async def pump(self, names, width: int):
        if type(width) is not int or width < 1:
            raise InfrastructureError("Mother's forest width must be a positive integer")
        if width > self.width:
            # asyncio.to_thread's default executor can silently cap concurrency below N.
            executor = ThreadPoolExecutor(max_workers=width, thread_name_prefix="forest-model")
            self.executors.append(executor)
            self.worker.model_executor = executor
            self.width = width
        errors = []
        for name, task in list(self.active.items()):
            if task.done():
                del self.active[name]
                try:
                    task.result()
                except Exception as exc:
                    errors.append(exc)
        if errors:
            try:
                await self.drain()
            finally:
                raise errors[0]
        for name in sorted(set(names)):
            nonce = name.split(".")[0]
            if name in self.active or nonce in self.worker.completed or nonce in self.worker.retired:
                continue
            if len(self.active) >= width:
                break
            self.active[name] = asyncio.create_task(self.worker.handle(name))

    async def drain(self):
        tasks = list(self.active.values())
        if not tasks:
            return
        completion = asyncio.gather(*tasks, return_exceptions=True)
        try:
            results = await asyncio.shield(completion)
        except asyncio.CancelledError:
            await completion
            raise
        finally:
            self.active.clear()
        for result in results:
            if isinstance(result, BaseException):
                raise result

    async def close(self):
        try:
            await self.drain()
        finally:
            for executor in self.executors:
                executor.shutdown(wait=True)
            self.executors.clear()
