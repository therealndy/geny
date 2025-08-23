"""Brian2-based sandbox (stub, no heavy deps required yet).

Controls will later adjust LLM temperature/style.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NeuroState:
    mood: float = 0.5
    sleep: float = 0.5
    stress: float = 0.5

    def to_temperature(self) -> float:
        # Simple mapping stub
        base = 0.7
        return max(0.1, min(1.5, base + (self.mood - self.stress) * 0.3))
