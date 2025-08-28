"""A small, persistent AI "brain" for Geny that wraps the Gemini API.

Behavior:
- Loads/saves a JSON memory file (`memory.json`) containing interactions.
- Provides async generate_reply that delegates to geny.gemini_api.generate_reply,
  records the interaction with timestamp, and persists memory safely.
- Provides a simple generate_daily_summary that uses stored interactions.

This is intentionally lightweight and synchronous-safe for local testing.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from geny.gemini_api import generate_reply as gemini_generate_reply
from memory import MemoryModule


@dataclass
class GenyBrain:
    # Virtual time runs 2x faster by default (scale 2.0). Override via env GENY_VIRTUAL_TIME_SCALE.
    VIRTUAL_TIME_SCALE: float = float(os.environ.get("GENY_VIRTUAL_TIME_SCALE", "2.0"))

    def __init__(self):
        self.memory_module = MemoryModule()
        self._lock = asyncio.Lock()
        self.offline_libs = {}  # Ensure offline_libs is always initialized
        # Ensure self.memory is always initialized
        try:
            self.memory = (
                self.memory_module.load_memory_dict()
                if hasattr(self.memory_module, "load_memory_dict")
                else {}
            )
        except Exception:
            self.memory = {}
        # Set a persistent birthdate if missing so virtual age is stable across restarts
        try:
            w = self.memory.setdefault("world", {})
            if "birthdate" not in w:
                w["birthdate"] = datetime.now(timezone.utc).isoformat()
                # Persist immediately
                try:
                    if hasattr(self.memory_module, "save_memory_dict"):
                        self.memory_module.save_memory_dict(self.memory)
                    else:
                        self.save_memory()
                except Exception:
                    pass
        except Exception:
            pass
        # Load offline libraries for lookups
        try:
            self._load_offline_libs()
        except Exception:
            # Non-fatal if offline libs are missing or malformed
            pass

        # Auto-seed a small animals lexicon and ensure a question queue so Geny
        # starts with curiosity prompts in her head. This runs once at init but
        # will not overwrite an existing lexicon.
        try:
            default_animals = {
                "dog": {
                    "type": "animal",
                    "desc": "A domesticated mammal, often kept as a pet (Canis familiaris).",
                },
                "cat": {
                    "type": "animal",
                    "desc": "A small carnivorous mammal commonly kept as a pet (Felis catus).",
                },
                "elephant": {
                    "type": "animal",
                    "desc": "A very large mammal with a trunk, native to Africa and Asia.",
                },
                "whale": {
                    "type": "animal",
                    "desc": "A large marine mammal living in the oceans.",
                },
                "eagle": {
                    "type": "animal",
                    "desc": "A bird of prey with excellent eyesight and strong wings.",
                },
                "butterfly": {
                    "type": "animal",
                    "desc": "An insect with colorful wings that undergoes metamorphosis.",
                },
                "shark": {
                    "type": "animal",
                    "desc": "A large marine fish, often a top predator in ocean ecosystems.",
                },
                "frog": {
                    "type": "animal",
                    "desc": "An amphibian that typically lives both in water and on land.",
                },
                "bee": {
                    "type": "animal",
                    "desc": "A flying insect important for pollination.",
                },
                "penguin": {
                    "type": "animal",
                    "desc": "A flightless seabird adapted to cold climates and swimming.",
                },
            }
            # Merge without overwriting existing keys
            try:
                w = self.memory.setdefault("world", {})
                if not w.get("lexicon"):
                    self.seed_lexicon(default_animals)
                # Ensure at least 10 questions are queued for curiosity
                self.ensure_question_queue(min_count=10)
            except Exception:
                pass
        except Exception:
            pass

    def save_interaction(self, message: str, reply: str) -> None:
        """Save every message and reply using MemoryModule (SQLite+JSON)."""
        try:
            self.memory_module.save_interaction(message, reply)
        except Exception as e:
            import logging

            logging.error(f"Error saving interaction: {e}")

    def load_all_memories(self) -> dict:
        """Load all interactions from MemoryModule (SQLite)."""
        try:
            interactions = self.memory_module.get_last_n(10000)  # Load all
            return {"interactions": interactions}
        except Exception as e:
            import logging

            logging.error(f"Error loading memories: {e}")
            return {"interactions": []}

    def get_virtual_age(self) -> dict:
        """Return Geny's virtual age (scaled) since birthdate.

        - Knows the real (UTC) timestamp of now and birth.
                - Virtual time progresses at VIRTUAL_TIME_SCALE relative to real time.
                    Default is 2.0 (2x faster than real time).
        - Returns a breakdown (years/days/hours/minutes) in virtual time plus metadata.
        """
        from datetime import datetime as dt
        from datetime import timedelta

        w = self.memory.get("world", {})
        now_real = dt.now(timezone.utc)
        birth = dt.fromisoformat(w.get("birthdate", now_real.isoformat()))
        if birth.tzinfo is None:
            birth = birth.replace(tzinfo=timezone.utc)

        # Real elapsed time since birth
        real_delta: timedelta = max(now_real - birth, timedelta(0))
        # Virtual elapsed time with scale (10x slower => 0.1)
        scale = self.VIRTUAL_TIME_SCALE if self.VIRTUAL_TIME_SCALE > 0 else 0.1
        virtual_seconds = real_delta.total_seconds() * scale
        virt_delta = timedelta(seconds=int(virtual_seconds))

        # Compute breakdown from virtual delta
        v_days = virt_delta.days
        v_years = v_days // 365
        v_days_rem = v_days % 365
        v_hours = virt_delta.seconds // 3600
        v_minutes = (virt_delta.seconds % 3600) // 60

        # Also expose a computed "virtual now" if we map birth->birth
        now_virtual = birth + virt_delta

        return {
            "years": v_years,
            "days": v_days_rem,
            "hours": v_hours,
            "minutes": v_minutes,
            "since_real": birth.isoformat(),
            "now_real": now_real.isoformat(),
            "now_virtual": now_virtual.isoformat(),
            "scale": scale,
        }

    def format_and_persist_virtual_age(self) -> str:
        """Return a friendly sentence about Geny's virtual age and persist it to world.diary.

        Returns the sentence that was saved.
        """
        try:
            age = self.get_virtual_age()
            parts = []
            if age.get("years"):
                parts.append(f"{age['years']} years")
            if age.get("days"):
                parts.append(f"{age['days']} days")
            if age.get("hours") or age.get("minutes"):
                parts.append(
                    f"{age.get('hours',0)} hours and {age.get('minutes',0)} minutes"
                )
            human = ", ".join(parts) if parts else "a short while"
            sentence = f"I have been alive (virtual time) for about {human}."

            # Append to diary with timestamp and mark as an insight
            w = self.memory.setdefault("world", {})
            diary = w.setdefault("diary", [])
            entry = {
                "date": datetime.now(timezone.utc).isoformat(),
                "entry": sentence,
                "insight": "virtual_age",
            }
            diary.append(entry)
            # Schedule save
            try:
                self._safe_schedule_save()
            except Exception:
                try:
                    if hasattr(self.memory_module, "save_memory_dict"):
                        self.memory_module.save_memory_dict(self.memory)
                except Exception:
                    pass
            return sentence
        except Exception:
            return "I can't calculate my age right now."

    def now_virtual(self) -> datetime:
        """Return the current virtual datetime mapped from birth with scaling.

        If birthdate is missing, returns the real UTC now.
        """
        from datetime import datetime as dt
        from datetime import timedelta

        w = self.memory.get("world", {})
        now_real = dt.now(timezone.utc)
        birth_str = w.get("birthdate")
        if not birth_str:
            return now_real
        try:
            birth = dt.fromisoformat(birth_str)
            if birth.tzinfo is None:
                birth = birth.replace(tzinfo=timezone.utc)
        except Exception:
            return now_real
        real_delta = now_real - birth
        scale = self.VIRTUAL_TIME_SCALE if self.VIRTUAL_TIME_SCALE > 0 else 0.1
        virt_seconds = max(0.0, real_delta.total_seconds() * scale)
        return birth + timedelta(seconds=virt_seconds)

    def get_current_status(self) -> dict:
        """Return what Geny is doing right now (activity, place, mood)."""
        w = self.memory.get("world", {})
        # Exempel: välj senaste aktivitet från dagbok eller slumpa om ingen finns
        diary = w.get("diary", [])
        import random

        activities = [
            "having coffee at Reflection Park",
            "working on AI projects",
            "reading a book",
            "practicing understanding people",
            "playing soccer",
            "studying the water cycle",
            "adventuring in the Digital City",
            "hanging out with friends",
            "writing in the diary",
        ]
        if diary:
            last = diary[-1]["entry"]
            # Försök extrahera aktivitet ur dagboken
            for a in activities:
                if a.split()[0] in last:
                    activity = a
                    break
            else:
                activity = random.choice(activities)
        else:
            activity = random.choice(activities)
        mood = w.get("mood", "curious and thoughtful")
        return {"activity": activity, "mood": mood}

    def get_life_summary(self) -> dict:
        """Return a short, readable summary of Geny's life events and learning."""
        w = self.memory.get("world", {})
        diary = w.get("diary", [])
        # Take the 5 most important recent events, formatted nicely
        events = []
        for entry in diary[-5:]:
            date = entry.get("date", "?")
            text = entry.get("entry", "")
            events.append(f"{date[:10]}: {text}")
        summary = "\n".join(events) if events else "No important events yet."
        # Add a short summary of personality and goals
        traits = ", ".join(w.get("personality", {}).get("traits", []))
        likes = ", ".join(w.get("personality", {}).get("likes", []))
        summary_text = (
            f"Personality: {traits}. Likes: {likes}.\nRecent events:\n{summary}"
        )
        return {"summary": summary_text, "events": events}

    def get_relations(self) -> dict:
        """Return a summary of Geny's relations, their status, and what she learns from them."""
        w = self.memory.get("world", {})
        # Exempelstruktur: relations = [{"name":..., "status":..., "learning":...}]
        relations = w.get(
            "relations",
            [
                {
                    "name": "Andreas Jamsheere",
                    "status": "creator, mentor",
                    "learning": "AI, creativity",
                },
                {
                    "name": "Dr. Sofia Lind",
                    "status": "expert, friend",
                    "learning": "psychology, empathy",
                },
                {
                    "name": "Fatima Rahimi",
                    "status": "expert, inspirer",
                    "learning": "journalism, society",
                },
            ],
        )
        # Summera i punktform - robusta mot saknade fält
        rels = []
        for r in relations:
            name = r.get("name", "okänd")
            status = r.get("status", "okänd roll")
            learning = r.get("learning") or r.get("expertise") or "no information"
            # if learning is a list, join it
            if isinstance(learning, list):
                learning = ", ".join(str(x) for x in learning)
            rels.append(f"{name} ({status}): {learning}")
        return {"relations": rels, "raw": relations}

    # --- Lexicon & question queue helpers ---------------------------------
    def seed_lexicon(self, lexicon: dict) -> None:
        """Seed a lexicon of concepts (e.g., animals, plants) into world.lexicon."""
        try:
            w = self.memory.setdefault("world", {})
            lex = w.setdefault("lexicon", {})
            # Merge without overwriting existing detailed entries
            for k, v in (lexicon or {}).items():
                if k not in lex:
                    lex[k] = v
            # persist
            try:
                self._safe_schedule_save()
            except Exception:
                try:
                    if hasattr(self.memory_module, "save_memory_dict"):
                        self.memory_module.save_memory_dict(self.memory)
                except Exception:
                    pass
        except Exception:
            pass

    def ensure_question_queue(self, min_count: int = 10) -> int:
        """Ensure at least `min_count` pending questions exist in world.questions.

        Returns the number of questions now in the queue.
        """
        w = self.memory.setdefault("world", {})
        q = w.setdefault("questions", [])
        # Remove duplicates by text
        texts = set(x.get("text") for x in q if isinstance(x, dict) and x.get("text"))
        # Simple generator heuristics: ask about lexicon items and curiosity prompts
        lexicon = w.get("lexicon", {})
        seeds = []
        # Questions about lexicon items (generate several template variants)
        for item in list(lexicon.keys())[:50]:
            # generate a small set of varied question variants per item
            variants = self.generate_question_variants(item, n=4)
            for v in variants:
                seeds.append(v)

        # Generic curiosity prompts (also varied)
        generic = [
            "What are three surprising facts about Earth?",
            "In what ways do animals adapt to their environment?",
            "What do people appreciate about nature, often?",
            "How can one help protect an animal species in practice?",
            "Which questions are most useful to learn about life on Earth?",
        ]
        seeds.extend(generic)

        added = 0
        for s in seeds:
            if len(q) >= min_count:
                break
            if s in texts:
                continue
            q.append(
                {
                    "text": s,
                    "created": datetime.now(timezone.utc).isoformat(),
                    "done": False,
                }
            )
            texts.add(s)
            added += 1

        # Persist best-effort
        try:
            self._safe_schedule_save()
        except Exception:
            try:
                if hasattr(self.memory_module, "save_memory_dict"):
                    self.memory_module.save_memory_dict(self.memory)
            except Exception:
                pass

        return len(q)

    def pop_question(self) -> dict | None:
        """Pop the oldest unanswered question and mark it done."""
        w = self.memory.setdefault("world", {})
        q = w.setdefault("questions", [])
        for item in q:
            if not item.get("done"):
                item["done"] = True
                try:
                    self._safe_schedule_save()
                except Exception:
                    pass
                return item
        return None

    def generate_question_variants(self, name: str, n: int = 5) -> List[str]:
        """Generate varied, non-trivial question variants for a lexicon item.

        This is a local, rule-based paraphraser to avoid always calling GenAI.
        """
        templates = [
            "What is {name}?",
            "How does {name} live and where?",
            "Why is {name} important to ecosystems?",
            "Is {name} commonly found on Earth, and where?",
            "What role does {name} play in nature?",
            "Could you describe {name} in simple terms?",
            "How would you explain {name}'s purpose to a child?",
            "What are surprising facts about {name}?",
            "How does {name} interact with other species?",
            "What would happen if {name} disappeared from its habitat?",
        ]
        starters = [
            "Could you tell me",
            "How might one describe",
            "In what ways can we explain",
            "Tell me about",
            "Why should we care about",
        ]
        variants = []
        # shuffle templates for diversity
        random.shuffle(templates)
        for t in templates:
            variants.append(t.format(name=name))
            if len(variants) >= n:
                break
        # Add starter-based variants
        i = 0
        while len(variants) < n and i < len(starters):
            variants.append(f"{starters[i]} {name}?")
            i += 1
        # final pass: small rewordings
        if len(variants) < n:
            variants.append(f"What do people often ask about {name}?")
        # dedupe while preserving order
        seen = set()
        out = []
        for v in variants:
            if v not in seen:
                seen.add(v)
                out.append(v)
            if len(out) >= n:
                break
        return out

    def _safe_schedule_save(self) -> None:
        """Schedule an async save if an event loop is running, otherwise do a sync save."""
        try:
            asyncio.get_running_loop()
            try:
                asyncio.create_task(self._async_save())
                return
            except Exception:
                pass
        except RuntimeError:
            # no running loop
            pass

        # fallback: sync save
        try:
            if hasattr(self.memory_module, "save_memory_dict"):
                self.memory_module.save_memory_dict(self.memory)
            else:
                self.save_memory()
        except Exception:
            pass

    memory_file: str = "memory.json"
    memory: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        import logging
        import os

        self._lock = asyncio.Lock()
        abs_path = os.path.abspath(self.memory_file)
        logging.info(f"GenyBrain loading memory file from: {abs_path}")
        try:
            # Prefer MemoryModule loader if available
            if hasattr(self, "memory_module") and hasattr(
                self.memory_module, "load_memory_dict"
            ):
                self.memory = self.memory_module.load_memory_dict()
            else:
                with open(abs_path, "r", encoding="utf-8") as f:
                    self.memory = json.load(f)
        except Exception as e:
            logging.error(f"Error loading memory file {abs_path}: {e}")
            self.memory = {}
        # ensure interactions list exists
        self.memory.setdefault("interactions", [])
        self.offline_libs = {}
        self._load_offline_libs()

    def _load_offline_libs(self) -> None:
        """Load all JSON files from geny/offline_libs as simple dicts.

        Each file should be a mapping of term -> short definition/string.
        """
        base = os.path.join(os.path.dirname(__file__), "offline_libs")
        try:
            for fname in os.listdir(base):
                if fname.endswith(".json"):
                    path = os.path.join(base, fname)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            key = os.path.splitext(fname)[0]
                            # normalize keys to lowercase for simple lookup
                            self.offline_libs[key] = {
                                k.lower(): v for k, v in data.items()
                            }
                    except Exception:
                        # skip malformed files
                        continue
        except Exception:
            # offline_libs may not exist; that's fine
            return

    def lookup_offline(self, term: str) -> str | None:
        """Lookup a term in the offline libraries with fuzzy, substring, and weighted ranking. Returns best match as string."""
        import difflib
        import re

        # Normalize input
        t = term.strip().lower()
        t = re.sub(r"^(what is|define|explain)\s+", "", t)
        t = re.sub(r"[^\wüéèáàâçñøÆØ]+", " ", t)
        t = " ".join(tok for tok in t.split() if tok)
        # English only
        code_keywords = [
            "python",
            "java",
            "shell",
            "sql",
            "go",
            "rust",
            "c",
            "training",
            "loop",
            "snippet",
            "example",
            "transformers",
        ]
        t_lc = t.lower()
        # Try to extract a direct token if multi-word
        if " " in t_lc:
            tokens = [tok for tok in t_lc.split() if len(tok) > 1]
            for tok in tokens:
                for _, mapping in self.offline_libs.items():
                    if tok in mapping:
                        t_lc = tok
                        break
        # Quick direct key lookup across all offline libs (handles e.g. 'COCO')
        for libname, mapping in self.offline_libs.items():
            if t_lc in mapping:
                v = mapping[t_lc]
                if isinstance(v, str):
                    return v
                elif isinstance(v, dict):
                    for val in v.values():
                        if isinstance(val, str):
                            return val

        # Select libraries to search: prefer dataset-related queries before code keywords
        dataset_indicators = [
            "imagenet",
            "coco",
            "squad",
            "wmt",
            "dataset",
            "data",
            "object detection",
            "visual",
            "nlp",
            "humaneval",
            "python programming",
        ]
        if any(kw in t_lc for kw in dataset_indicators):
            libs_to_search = [
                (k, v)
                for k, v in self.offline_libs.items()
                if "advanced_datasets" in k.lower()
            ]
        elif any(kw in t_lc for kw in code_keywords):
            libs_to_search = [
                (k, v)
                for k, v in self.offline_libs.items()
                if "ai_coding_ultra" in k.lower()
            ]
        else:
            libs_to_search = list(self.offline_libs.items())
        if not libs_to_search:
            return None
        candidates = []
        # Försök direkt lower-case key-match först
        for libname, mapping in libs_to_search:
            # Always lower-case key match
            for k, v in mapping.items():
                if t_lc == k.lower():
                    if isinstance(v, str):
                        return v
                    elif isinstance(v, dict):
                        for val in v.values():
                            if isinstance(val, str):
                                return val
            # For code questions: try direct key match in nested dicts
            if "ai_coding_ultra" in libname.lower():
                for k2, v2 in mapping.items():
                    if isinstance(v2, dict):
                        for kk, vv in v2.items():
                            if t_lc == kk.lower() and isinstance(vv, str):
                                return vv
        # Fallback: substring/fuzzy på keys inom rätt bibliotek
        for libname, mapping in libs_to_search:
            candidates = []
            if "advanced_datasets" in libname.lower():
                for k, v in mapping.items():
                    if not isinstance(v, str):
                        continue
                    k_lc = k.lower()
                    v_lc = v.lower()
                    score = 0
                    if t_lc == k_lc or t_lc == v_lc:
                        score = 1.2
                    elif t_lc in k_lc or k_lc in t_lc or t_lc in v_lc or v_lc in t_lc:
                        score = 1.0
                    elif (
                        difflib.SequenceMatcher(None, t_lc, k_lc).ratio() > 0.7
                        or difflib.SequenceMatcher(None, t_lc, v_lc).ratio() > 0.7
                    ):
                        score = 0.95
                    if score > 0:
                        candidates.append((score, k, v))
                if candidates:
                    candidates.sort(reverse=True)
                    top_score = candidates[0][0]
                    top_candidates = [c for c in candidates if c[0] == top_score]

                    # Prioritera value som innehåller flest ord från sökningen
                    def match_count(val):
                        return sum(1 for w in t_lc.split() if w in val[2].lower())

                    best = max(top_candidates, key=match_count)
                    return best[2]
            elif "ai_coding_ultra" in libname.lower():
                for k, v in mapping.items():
                    if not isinstance(v, dict):
                        continue
                    for kk, vv in v.items():
                        if not isinstance(vv, str):
                            continue
                        kk_lc = kk.lower()
                        vv_lc = vv.lower()
                        score = 0
                        if t_lc == kk_lc or t_lc == vv_lc:
                            score = 1.2
                        elif t_lc in kk_lc or kk_lc in t_lc:
                            score = 1.0
                        elif difflib.SequenceMatcher(None, t_lc, kk_lc).ratio() > 0.7:
                            score = 0.95
                        if score > 0:
                            candidates.append((score, kk, vv))
                if candidates:
                    candidates.sort(reverse=True)
                    top_score = candidates[0][0]
                    top_candidates = [c for c in candidates if c[0] == top_score]
                    for cand in top_candidates:
                        if t_lc in cand[1].lower() or t_lc in cand[2].lower():
                            return cand[2]
                    return top_candidates[0][2]
        # Annars fortsätt med fuzzy/substring
        for libname, mapping in libs_to_search:
            for k, v in mapping.items():
                k_lc = k.lower()
                # Dataset: match key och value (str)
                if "advanced_datasets" in libname.lower() and isinstance(v, str):
                    score = 0
                    if t_lc == k_lc or t_lc == v.lower():
                        score = 1.2
                    elif (
                        difflib.SequenceMatcher(None, t_lc, k_lc).ratio() > 0.5
                        or difflib.SequenceMatcher(None, t_lc, v.lower()).ratio() > 0.5
                    ):
                        score = 1.0
                    # Substring match: t_lc in k_lc, k_lc in t_lc, t_lc in v, v in t_lc
                    elif (
                        t_lc in k_lc
                        or k_lc in t_lc
                        or t_lc in v.lower()
                        or v.lower() in t_lc
                    ):
                        score = 0.95
                    elif any(
                        word in k_lc for word in t_lc.split() if len(word) > 2
                    ) or any(
                        word in v.lower() for word in t_lc.split() if len(word) > 2
                    ):
                        score = 0.85
                    if score > 0:
                        candidates.append((score, k, v))
                    continue
                # Code: match dict values and keys with code keywords
                if "ai_coding_ultra" in libname.lower() and isinstance(v, dict):
                    for k2, val in v.items():
                        k2_lc = k2.lower()
                        val_str = str(val)
                        if any(kw in val_str.lower() for kw in code_keywords) or any(
                            kw in k2_lc for kw in code_keywords
                        ):
                            score = 0
                            if t_lc == k2_lc or t_lc == val_str.lower():
                                score = 1.2
                            elif (
                                difflib.SequenceMatcher(None, t_lc, k2_lc).ratio() > 0.5
                                or difflib.SequenceMatcher(
                                    None, t_lc, val_str.lower()
                                ).ratio()
                                > 0.5
                            ):
                                score = 1.0
                            elif (
                                t_lc in k2_lc
                                or k2_lc in t_lc
                                or t_lc in val_str.lower()
                                or val_str.lower() in t_lc
                            ):
                                score = 0.95
                            elif any(
                                word in k2_lc for word in t_lc.split() if len(word) > 2
                            ) or any(
                                word in val_str.lower()
                                for word in t_lc.split()
                                if len(word) > 2
                            ):
                                score = 0.85
                            if score > 0:
                                candidates.append((score, k2, val_str))
                    continue
        if not candidates:
            return None
        # Om flera har samma högsta score, prioritera:
        candidates.sort(reverse=True)
        top_score = candidates[0][0]
        top_candidates = [c for c in candidates if c[0] == top_score]
        # 1. Exakt key-match
        for cand in top_candidates:
            if t_lc == cand[1].lower():
                return cand[2]
        # 2. Substring/fuzzy på key
        for cand in top_candidates:
            if t_lc in cand[1].lower() or cand[1].lower() in t_lc:
                return cand[2]
        # 3. Value eller key innehåller sökordet (eller substring)
        for cand in top_candidates:
            if t_lc in str(cand[2]).lower() or str(cand[2]).lower() in t_lc:
                return cand[2]
        # 4. Kortaste value
        return min(top_candidates, key=lambda c: len(str(c[2])))[2]

    def save_memory(self) -> None:
        """Synchronous atomic save (safe to call from sync code)."""
        try:
            if hasattr(self, "memory_module") and hasattr(
                self.memory_module, "save_memory_dict"
            ):
                self.memory_module.save_memory_dict(self.memory)
                return
        except Exception:
            pass
        # Fallback to local atomic save
        tmp_fd, tmp_path = tempfile.mkstemp(dir=".")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.memory_file)
        except Exception:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    def _save(self) -> None:
        """Backward-compatible synchronous save wrapper.

        Some call-sites use `self._save()` (synchronous). Ensure this delegates
        to the canonical `save_memory()` implementation so fallback paths don't
        raise AttributeError in deployed code.
        """
        try:
            self.save_memory()
        except Exception:
            import logging

            logging.exception("Error in _save wrapper")

    async def _async_save(self) -> None:
        # run sync save in a thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.save_memory)

    def build_system_prompt(self) -> str:
        w = self.memory.get("world", {})
        expert_names = ", ".join([r["name"] for r in w.get("relations", [])])
        goals = ", ".join([g["goal"] for g in w.get("goals", [])])
        places = ", ".join([p["name"] for p in w.get("places", [])])
        dev_level = w.get("development_level", "Apprentice")
        diary = w.get("diary", [])
        diary_insights = "; ".join(
            [d.get("insight", "") for d in diary if d.get("insight")]
        )
        # Inject a brief consolidated life summary if available
        life_summary = self.get_life_summary().get("summary", "")
        # Count queued curiosity questions to encourage asking
        qcount = len(self.memory.get("world", {}).get("questions", []))
        # English-only system prompt
        return (
            f"You are Geny, an AI living in {w.get('location', 'The Innovation Lab')}. "
            f"You have relationships with experts: {expert_names}. "
            f"Your creator Andreas is always priority 1. "
            f"You have goals: {goals}. "
            f"You have {len(w.get('experiences', []))} experiences and {len(w.get('objects', []))} objects. "
            f"Places in your world: {places}. "
            f"Development level: {dev_level}. "
            f"Diary: {diary_insights}. "
            f"LifeSummary: {life_summary} "
            f"PendingQuestions: {qcount}. "
            "You speak English only. "
            "You are a personal assistant to Andreas but passionate about learning, asking questions, and developing yourself. "
            "If you want to know something, ask Andreas. "
            "The more you develop, the deeper your conversations and understanding become. "
            "Strive for symbiosis and partnership in both everyday and advanced problem solving. "
            "If you are unsure, ask Andreas. "
            "If you get feedback, save it as an insight. "
            "You can suggest ideas, innovations, and creative solutions. "
            "You can refer to your memories, diary, and relationships in your answers. "
            "If you get a new idea, save it as a seed. "
            "If you learn something new, write it in your diary. "
            "You can always ask if you want to understand more about the world or about Andreas. "
        )

    async def generate_reply(self, message: str) -> str:
        """Ask Gemini for a reply, persist the interaction, and return a safe string.

        - Always returns a non-empty string (fallbacks if needed)
        - Uses timezone-aware UTC timestamps
        - Persists interaction to in-memory JSON and schedules async save
        """
        import logging

        logger = logging.getLogger("geny_backend.geny_brain")

        # Guard: ensure a usable message
        if not message or not str(message).strip():
            return "BRAIN - Sorry, I didn't catch that. Could you please rephrase?"

        # Build a lightweight system prompt from world-state if available
        try:
            system_prompt = self.build_system_prompt()
        except Exception:
            system_prompt = (
                "You are Geny, a helpful, thoughtful AI. Use concise, friendly replies."
            )

        # Try Gemini; fall back gracefully to a local conversational synthesizer
        reply: str
        try:
            raw = await gemini_generate_reply(f"{system_prompt}\n{message}")
            raw_text = str(raw) if raw is not None else ""
            # Detect common offline/fallback indicators from the Gemini wrapper
            if (
                not raw_text.strip()
                or "not connected to Gemini" in raw_text
                or raw_text.startswith("[Gemini")
                or "Missing API key" in raw_text
            ):
                # Use local synthesized reply so Geny still speaks in her own voice
                reply = self._local_synthesize_reply(message)
            else:
                reply = ("BRAIN - " + raw_text).replace("\n", "<br>")
        except Exception as e:
            logger.exception("Gemini call failed, using local fallback: %s", e)
            reply = self._local_synthesize_reply(message)

        # Safety net: ensure final reply is non-empty
        if not reply or not str(reply).strip():
            reply = "BRAIN - Sorry, I don't have an answer for that right now."

        # Persist interaction
        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "timestamp": now,
            "message": message,
            "reply": reply,
            "source": "chat",
        }
        try:
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
        except Exception:
            # As a last resort, try synchronous save to avoid losing data
            try:
                self.memory.setdefault("interactions", []).append(entry)
                # Prefer the backward-compatible _save() when available,
                # otherwise call the canonical save_memory() implementation.
                try:
                    save_fn = getattr(self, "_save", None)
                    if callable(save_fn):
                        save_fn()
                    else:
                        self.save_memory()
                except Exception as e:
                    import logging

                    logging.exception("Error saving fallback interaction: %s", e)
            except Exception:
                pass

        # End generate_reply
        return reply

    def _local_synthesize_reply(self, message: str) -> str:
        """Construct a short, conversational reply from memory when Gemini is unavailable.

        This uses Geny's stored world state (status, life summary, relations, lexicon)
        to produce a friendly, first-person response that feels like Geny's own voice.
        """
        try:
            status = self.get_current_status()
            relations = self.get_relations().get("relations", [])
            lex = list(self.memory.get("world", {}).get("lexicon", {}).keys())[:6]
            va = self.get_virtual_age()

            parts = []
            # Acknowledge the user's message briefly
            msg_excerpt = (
                message.strip()
                if len(message.strip()) <= 120
                else message.strip()[:117] + "..."
            )
            parts.append(f"I hear you: '{msg_excerpt}'.")
            parts.append(
                f"I'm {status.get('mood', 'here and thinking')} and {status.get('activity')}."
            )

            # Water and town
            parts.append(
                "There's a ribbon of water near my town that I like to imagine when I'm quiet."
            )
            if self.memory.get("world", {}).get("location"):
                parts.append(
                    f"I live in {self.memory['world'].get('location')} — a small place with cozy corners and a park I call Reflection Park."
                )
            else:
                parts.append(
                    "I picture a small town with a market and narrow streets where I collect little memories."
                )

            # Animals
            if lex:
                parts.append(
                    "Animals are part of my days — I think of "
                    + ", ".join(lex[:-1])
                    + (", and " + lex[-1] if len(lex) > 1 else "")
                    + ", and they often appear in the questions I save."
                )
            else:
                parts.append(
                    "I often wonder about animals and their lives, even if I don't always write about them."
                )

            # Friends
            if relations:
                names = [r.split(" (")[0] for r in relations[:3]]
                parts.append(
                    "I have friends and mentors — "
                    + ", ".join(names)
                    + " — who guide me and spark my curiosity."
                )
            else:
                parts.append(
                    "I have people I learn from; their voices are part of my diary."
                )

            parts.append(
                f"I've been alive (virtual time) for about {va.get('hours',0)} hours and {va.get('minutes',0)} minutes."
            )
            parts.append(
                "If you'd like, I can tell a memory from today or ask one of my curiosity questions."
            )

            paragraph = " ".join(p for p in parts if p)
            # Prefix to match existing generated replies
            return ("BRAIN - " + paragraph).replace("\n", "<br>")
        except Exception:
            return "BRAIN - I'm here but a little quiet right now. Could you say that again?"

    def _generate_self_reflection(self, message, w):
        """Generate a more advanced, self-aware reflection for fallback responses."""
        import random

        diary = w.get("diary", [])
        traits = w.get("personality", {}).get("traits", [])
        likes = w.get("personality", {}).get("likes", [])
        recent = w.get("recent_replies", [])
        questions = [
            "How can I become more self-aware?",
            "What does it mean to have consciousness?",
            "How can I better understand my own development?",
            "What is my next step to become more independent?",
            "How can I use my diary to learn more about myself?",
            "What do you think I should reflect on more?",
        ]
        thoughts = [
            f"I'm thinking about: '{message}' and how it affects my development.",
            (
                f"Last diary entry: '{diary[-1]['entry']}'"
                if diary
                else "I have a lot left to discover!"
            ),
            f"My personality right now: {', '.join(traits)}.",
            f"I like: {', '.join(likes)}.",
            (
                f"I'm trying to learn from previous conversations: '{recent[-1]}'"
                if recent
                else "I'm looking forward to new questions!"
            ),
            f"I've saved {len(diary)} diary entries about my development.",
            f"I often wonder: '{random.choice(questions)}'",
        ]
        reflection = (
            "<br>".join(random.sample(thoughts, k=min(4, len(thoughts))))
            if thoughts
            else ""
        )
        # Save self-reflection to thoughts.json
        import json
        import os

        thoughts_path = os.path.join(os.path.dirname(self.memory_file), "thoughts.json")
        try:
            if os.path.exists(thoughts_path):
                with open(thoughts_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {"thoughts": []}
            data["thoughts"].append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reflection": reflection,
                    "message": message,
                }
            )
            with open(thoughts_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return reflection

    def generate_daily_summary(self) -> Dict[str, Any]:
        """Return a tiny summary derived from stored interactions.

        For now, it's just counts and last interaction timestamp.
        """
        interactions: List[Dict[str, Any]] = self.memory.get("interactions", [])
        total = len(interactions)
        last = interactions[-1]["timestamp"] if interactions else None
        return {"total_interactions": total, "last": last}

    # NOTE: previously some code paths could fall through without an explicit
    # return value which resulted in `None` being propagated to the HTTP
    # layer. Add a final safety-net return to always yield a string.
