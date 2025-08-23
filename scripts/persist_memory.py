#!/usr/bin/env python3
"""Persist the current on-disk memory.json into the MemoryModule (SQLite + atomic JSON).

This ensures the JSON on disk is also synced into the sqlite DB and written atomically
via MemoryModule.save_memory_dict.
"""
import json
import os
from pathlib import Path

from memory import MemoryModule

MEM_PATH = os.environ.get("GENY_MEMORY_JSON") or "memory.json"

p = Path(MEM_PATH)
if not p.exists():
    print(f"Memory file {p} not found; nothing to persist.")
    raise SystemExit(1)

try:
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    print(f"Failed to load {p}: {e}")
    raise

mm = MemoryModule()
try:
    mm.save_memory_dict(data)
    print(f"Persisted memory to {mm.json_path} and sqlite {mm.db_path} successfully.")
except Exception as e:
    print(f"Failed to persist memory via MemoryModule: {e}")
    raise
