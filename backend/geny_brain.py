from typing import Any


class GenyBrain:
    """Tiny façade used by the app. Kept minimal for tests."""

    def __init__(self, config: Any | None = None):
        self.config = config or {}

    async def reply(self, text: str) -> str:
        return f"brain-reply: {text}"
