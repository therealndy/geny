"""Shared UI components/styles for chat.

The web_chat.html can mimic this style; Streamlit app uses the same message shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Role = Literal["user", "assistant", "system"]


@dataclass
class ChatMessage:
    role: Role
    content: str


DEFAULT_SYSTEM_PROMPT = (
    "You are Geny, empathetic and witty. Keep replies short, kind, and helpful."
)
