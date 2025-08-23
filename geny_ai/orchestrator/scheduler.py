"""Nightly tasks and AutoEvolve (stub)."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class AutoEvolve:
    mutation_prob: float = 0.1

    def maybe_mutate(self, params: dict) -> dict:
        if random.random() < self.mutation_prob:
            mutated = dict(params)
            # mutate a known param for experimentation
            if "temperature" in mutated:
                mutated["temperature"] = min(
                    1.5, max(0.1, mutated["temperature"] * 1.2)
                )
            else:
                mutated["temperature"] = 0.9
            mutated["mutated"] = True
            return mutated
        return params


def run_nightly(brain, memsvc, params: dict | None = None) -> dict:
    """Run nightly maintenance:
    - Generate and persist a daily summary
    - AutoEvolve mutate params (10% chance)
    - Return report with whether mutation happened
    """
    out = {"summary": None, "mutated": False, "params": params or {}}
    # Summary
    try:
        summary_text = brain.generate_daily_summary()
        # store in brain.memory under world.diary
        w = brain.memory.setdefault("world", {})
        diary = w.setdefault("diary", [])
        from datetime import datetime, timezone

        diary.append(
            {"date": datetime.now(timezone.utc).isoformat(), "entry": summary_text}
        )
        if hasattr(brain, "save_memory"):
            brain.save_memory()
        out["summary"] = summary_text
    except Exception:
        out["summary"] = None
    # Mutation
    evo = AutoEvolve()
    before = dict(out["params"]) if out["params"] else {}
    after = evo.maybe_mutate(before)
    out["mutated"] = after != before
    out["params"] = after
    return out
