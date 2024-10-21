from functools import partial
from typing import Any, Callable, Coroutine


class EventHandler:
    def __init__(self) -> None:
        self.subscribers: dict[str, list[Callable[[], Coroutine[Any, Any, None]]]] = {}

    def subscribe(
        self, event_name: str, fn: Callable[..., Coroutine[Any, Any, None]], *args: Any
    ) -> None:
        if event_name not in self.subscribers:
            self.subscribers[event_name] = []

        self.subscribers[event_name].append(partial(fn, *args))

    async def publish(self, event_name: str) -> None:
        if event_name not in self.subscribers:
            return
        for callback in self.subscribers[event_name]:
            await callback()
