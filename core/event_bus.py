"""
core/event_bus.py - Central Pub/Sub Asynchronous Event Router
"""
import asyncio
from typing import Callable, Dict, List, Any


class EventBus:

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable):
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    async def publish(self, event_name: str, payload: Any):
        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                if asyncio.iscoroutinefunction(callback):
                    await callback(payload)
                else:
                    callback(payload)
