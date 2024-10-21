from typing import Any


class EventHandler:
    def __init__(self) -> None:
        self.subscribers: dict[str, list[Any]] = {}

    def subscribe(self, event_name: str, callback: Any) -> None:
        if event_name not in self.subscribers:
            self.subscribers[event_name] = []

        self.subscribers[event_name].append(callback)

    async def publish(self, event_name: str) -> None:
        if event_name not in self.subscribers:
            return
        for callback in self.subscribers[event_name]:
            await callback()
