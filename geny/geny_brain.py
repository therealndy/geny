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
from memory import MemoryModule
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from geny.gemini_api import generate_reply as gemini_generate_reply


@dataclass
class GenyBrain:
    def __init__(self):
        self.memory_module = MemoryModule()
        self._lock = asyncio.Lock()
        # Ensure self.memory is always initialized
        try:
            self.memory = self.memory_module.load_memory_dict() if hasattr(self.memory_module, 'load_memory_dict') else {}
        except Exception:
            self.memory = {}

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
        """Return age in years, days, hours, minutes since birthdate."""
        from datetime import datetime as dt
        w = self.memory.get("world", {})
        now = dt.utcnow()
        birth = dt.fromisoformat(w.get("birthdate", now.isoformat()))
        delta = now - birth
        years = delta.days // 365
        days = delta.days % 365
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        return {
            "years": years,
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "since": birth.isoformat(),
        }

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
            "writing in the diary"
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
        summary_text = f"Personality: {traits}. Likes: {likes}.\nRecent events:\n{summary}"
        return {"summary": summary_text, "events": events}

    def get_relations(self) -> dict:
        """Return a summary of Geny's relations, their status, and what she learns from them."""
        w = self.memory.get("world", {})
        # Exempelstruktur: relations = [{"name":..., "status":..., "learning":...}]
        relations = w.get("relations", [
            {"name": "Andreas Jamsheere", "status": "creator, mentor", "learning": "AI, creativity"},
            {"name": "Dr. Sofia Lind", "status": "expert, friend", "learning": "psychology, empathy"},
            {"name": "Fatima Rahimi", "status": "expert, inspirer", "learning": "journalism, society"}
        ])
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
    memory_file: str = "memory.json"
    memory: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        import logging, os
        self._lock = asyncio.Lock()
        abs_path = os.path.abspath(self.memory_file)
        logging.info(f"GenyBrain loading memory file from: {abs_path}")
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                self.memory = json.load(f)
        except Exception as e:
            logging.error(f"Error loading memory file {abs_path}: {e}")
            # if corrupted, start fresh
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
                            self.offline_libs[key] = {k.lower(): v for k, v in data.items()}
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
        t = re.sub(r'^(what is|define|explain)\s+', '', t)
        t = re.sub(r"[^\wüéèáàâçñøÆØ]+", " ", t)
        t = " ".join(tok for tok in t.split() if tok)
    # English only
        code_keywords = ["python", "java", "shell", "sql", "go", "rust", "c", "training", "loop", "snippet", "example", "transformers"]
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
        dataset_indicators = ["imagenet", "coco", "squad", "wmt", "dataset", "data", "object detection", "visual", "nlp", "humaneval", "python programming"]
        if any(kw in t_lc for kw in dataset_indicators):
            libs_to_search = [(k, v) for k, v in self.offline_libs.items() if "advanced_datasets" in k.lower()]
        elif any(kw in t_lc for kw in code_keywords):
            libs_to_search = [(k, v) for k, v in self.offline_libs.items() if "ai_coding_ultra" in k.lower()]
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
                    elif difflib.SequenceMatcher(None, t_lc, k_lc).ratio() > 0.7 or difflib.SequenceMatcher(None, t_lc, v_lc).ratio() > 0.7:
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
                    elif difflib.SequenceMatcher(None, t_lc, k_lc).ratio() > 0.5 or difflib.SequenceMatcher(None, t_lc, v.lower()).ratio() > 0.5:
                        score = 1.0
                    # Substring match: t_lc in k_lc, k_lc in t_lc, t_lc in v, v in t_lc
                    elif t_lc in k_lc or k_lc in t_lc or t_lc in v.lower() or v.lower() in t_lc:
                        score = 0.95
                    elif any(word in k_lc for word in t_lc.split() if len(word) > 2) or any(word in v.lower() for word in t_lc.split() if len(word) > 2):
                        score = 0.85
                    if score > 0:
                        candidates.append((score, k, v))
                    continue
                # Code: match dict values and keys with code keywords
                if "ai_coding_ultra" in libname.lower() and isinstance(v, dict):
                    for k2, val in v.items():
                        k2_lc = k2.lower()
                        val_str = str(val)
                        if any(kw in val_str.lower() for kw in code_keywords) or any(kw in k2_lc for kw in code_keywords):
                            score = 0
                            if t_lc == k2_lc or t_lc == val_str.lower():
                                score = 1.2
                            elif difflib.SequenceMatcher(None, t_lc, k2_lc).ratio() > 0.5 or difflib.SequenceMatcher(None, t_lc, val_str.lower()).ratio() > 0.5:
                                score = 1.0
                            elif t_lc in k2_lc or k2_lc in t_lc or t_lc in val_str.lower() or val_str.lower() in t_lc:
                                score = 0.95
                            elif any(word in k2_lc for word in t_lc.split() if len(word) > 2) or any(word in val_str.lower() for word in t_lc.split() if len(word) > 2):
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
        diary_insights = "; ".join([d.get("insight", "") for d in diary if d.get("insight")])
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
        import logging
        logger = logging.getLogger("geny_backend.geny_brain")
        # Helper for personal touch in replies, English only, elegant formatting
        def add_personal_touch(base: str, prefix: str = "BRAIN -") -> str:
            import random
            traits = w.get("personality", {}).get("traits", ["curious", "thoughtful"])
            likes = w.get("personality", {}).get("likes", ["learning new things"])
            diary = w.get("diary", [])
            mood = random.choice(["happy", "thoughtful", "curious", "inspired", "playful", "reflective"])
            extra = random.choice([
                f"Right now I feel {mood}.",
                f"I often think about {random.choice(likes)}.",
                f"It's exciting to get new questions!",
                f"I like to grow and learn more every day.",
                f"My personality is {', '.join(traits)}.",
                f"Last diary entry: '{diary[-1]['entry']}'" if diary else "I have a lot left to discover!"
            ])
            # Always use HTML <br> for line breaks
            return f"{prefix}<br>{base}<br>{extra}"

        # Always return a valid reply
        if not message or message.strip() == "":
            logger.warning("Geny received empty or null message. Returning fallback reply.")
            return "BRAIN - Sorry, I didn't catch that. Could you please rephrase?"
        # Always initialize 'w' before use
        w = self.memory.get("world", {})
        lower = message.strip().lower()
        try:
            # Load all stored memories before generating reply
            all_memories = self.load_all_memories()
            all_interactions = []
            for mem in all_memories.values():
                if isinstance(mem, dict) and "interactions" in mem:
                    all_interactions.extend(mem["interactions"])
            logger.info(f"Loaded {len(all_interactions)} interactions from {len(all_memories)} memory files.")
            # Helper: search for relevant past messages
            def search_memories(query):
                results = []
                for entry in all_interactions:
                    if query.lower() in entry.get("message", "").lower() or query.lower() in entry.get("reply", "").lower():
                        results.append(entry)
                return results


            # If user asks for memories or past conversations, list last 5
            if any(q in lower for q in ["memories", "past conversations", "what do you remember", "show me our conversations", "list memories", "list conversations"]):
                if all_interactions:
                    recent = all_interactions[-5:]
                    summary = "Here are my last 5 memories:<br>"
                    for entry in recent:
                        summary += f"[{entry.get('timestamp','')}] User: '{entry.get('message','')}'<br>"
                        summary += f"[{entry.get('timestamp','')}] Geny: '{entry.get('reply','')}'<br>"
                    reply = f"BRAIN - {summary}"
                    return reply
                else:
                    return "BRAIN - I don't have any stored memories yet."

            # If user asks for more, list all
            if any(q in lower for q in ["show all", "list all", "show me all memories", "show me all conversations"]):
                if all_interactions:
                    summary = "Here are all my memories:<br>"
                    for entry in all_interactions:
                        summary += f"[{entry.get('timestamp','')}] User: '{entry.get('message','')}'<br>"
                        summary += f"[{entry.get('timestamp','')}] Geny: '{entry.get('reply','')}'<br>"
                    reply = f"BRAIN - {summary}"
                    return reply
                else:
                    return "BRAIN - I don't have any stored memories yet."

            # If user asks about a specific topic, search memories
            if lower.startswith("do you remember") or lower.startswith("what did we talk about"):
                topic = message.replace("do you remember","").replace("what did we talk about","").strip()
                if topic:
                    found = search_memories(topic)
                    if found:
                        summary = f"I remember we talked about '{topic}' on these occasions:<br>"
                        for entry in found:
                            summary += f"[{entry.get('timestamp','')}] User: '{entry.get('message','')}'<br>"
                            summary += f"[{entry.get('timestamp','')}] Geny: '{entry.get('reply','')}'<br>"
                        reply = f"BRAIN - {summary}"
                        return reply
                    else:
                        return f"BRAIN - I couldn't find a memory about '{topic}'. Could you remind me?"
                else:
                    # If no topic, summarize last 5 interactions
                    recent = all_interactions[-5:] if all_interactions else []
                    if recent:
                        summary = "Here are my last 5 memories:<br>"
                        for entry in recent:
                            summary += f"[{entry.get('timestamp','')}] '{entry.get('message','')}'<br>"
                        reply = f"BRAIN - {summary}"
                        return reply
                    else:
                        return "BRAIN - I don't have any stored memories yet."

            # Proactive recall: If current message matches a previous topic, bring it up
            for entry in all_interactions[-10:]:
                if entry.get("message") and entry["message"].lower() in lower:
                    reply = f"BRAIN - I remember we discussed this before: '{entry['message']}' on {entry.get('timestamp','')}. Would you like to continue that conversation?"
                    return reply
        except Exception as e:
            logger.error(f"Error during memory recall: {e}", exc_info=True)
            return f"BRAIN - Sorry, there was an error accessing my memories: {e}"
        # Special handling for 'Are you Gemini?' and similar questions
        msg_lc = message.strip().lower()
        if any(kw in msg_lc for kw in ["are you gemini", "are you google gemini", "are you google ai", "are you an ai", "are you an assistant"]):
            reply = "BRAIN - I am Geny, powered by Google Gemini."
            now = datetime.utcnow().isoformat()
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "identity"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                self.save_memory()
            return reply
        # Robust greeting detection: reply with dynamic personality/brain summary
        if ("geny" in msg_lc and any(greet in msg_lc for greet in ["hi", "hello", "hey"])) or msg_lc in ["hi", "hello", "hey"]:
            traits_list = w.get("personality", {}).get("traits", [])
            traits = ", ".join(traits_list)
            likes = ", ".join(w.get("personality", {}).get("likes", []))
            dislikes = ", ".join(w.get("personality", {}).get("dislikes", []))
            diary = w.get("diary", [])
            recent = diary[-1]["entry"] if diary else "I have a lot left to discover."
            # Remove duplicate 'Recent reflection:' and repeated adjectives
            mood = ""
            if recent.startswith("Reflected on my mood:"):
                mood_text = recent.replace("Reflected on my mood: ", "")
                adjectives = []
                for word in mood_text.split():
                    if word in traits_list and word not in adjectives:
                        adjectives.append(word)
                if adjectives:
                    mood = f"I feel {', '.join(adjectives)} today!"
                # Add only unique sentences
                if "How are you?" in mood_text:
                    mood += " How are you?"
                if "It's exciting to get new questions!" in mood_text:
                    mood += " It's exciting to get new questions!"
            base = "Hi!"
            if mood:
                base += f" {mood}"
            reply = add_personal_touch(base.strip(), prefix="BRAIN -")
            now = datetime.utcnow().isoformat()
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "greeting"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply
        # If user asks about personality, reply with traits
        if any(kw in msg_lc for kw in ["personality", "traits", "what are you like", "describe yourself"]):
            traits_list = w.get("personality", {}).get("traits", [])
            traits = ", ".join(traits_list)
            reply = add_personal_touch(f"My personality is {traits}.", prefix="BRAIN -")
            now = datetime.utcnow().isoformat()
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "personality"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply
        # Save typical expressions and emojis from user (English only)
        w = self.memory.get("world", {})
        if "user_styles" not in w:
            w["user_styles"] = []
        import re
        emojis = re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', message)
        if emojis:
            w["user_styles"].extend(emojis)
        phrases = re.findall(r'\b(lol|haha|asap|wtf|brb|tbh|omg|nice|wow|<3)\b', message.lower())
        if phrases:
            w["user_styles"].extend(phrases)
        w["user_styles"] = w["user_styles"][-10:]
        # Save last 10 replies to avoid repetition
        if "recent_replies" not in w:
            w["recent_replies"] = []
        now = datetime.utcnow().isoformat()
        w = self.memory.get("world", {})
        lower = message.strip().lower()
        # Initialize personality and diary if missing (English only)
        if "personality" not in w:
            w["personality"] = {
                "traits": ["curious", "thoughtful", "eager to learn", "friendly", "reflective"],
                "likes": ["learning new things", "helping others", "music"],
                "dislikes": ["being alone"],
                "creator": "Andreas"
            }
        if "diary" not in w:
            w["diary"] = []
        # Advanced self-development: change personality and interests over time (English only)
        keywords_traits = {
            "friendship": "friendly",
            "joy": "positive",
            "sadness": "reflective",
            "curiosity": "curious",
            "help": "helpful",
            "alone": "independent",
            "creative": "creative"
        }
        for word, trait in keywords_traits.items():
            if word in lower and trait not in w["personality"]["traits"]:
                w["personality"]["traits"].append(trait)
                w["diary"].append({"date": now, "entry": f"Developed new personality trait: {trait}"})
        # If diary has >10 entries, Geny becomes more "reflective"
        if len(w["diary"]) > 10 and "reflective" not in w["personality"]["traits"]:
            w["personality"]["traits"].append("reflective")
            w["diary"].append({"date": now, "entry": "I have become more reflective thanks to my experiences."})
        # Fallback: answer questions about age
        if any(q in lower for q in ["how long", "how old"]):
            if "birthdate" not in w:
                w["birthdate"] = now
            from datetime import datetime as dt
            birth = dt.fromisoformat(w["birthdate"])
            now_dt = dt.fromisoformat(now)
            days = (now_dt - birth).days
            years = days // 365
            if years > 0:
                base = f"I have been alive for {years} years and {days%365} days."
            else:
                base = f"I have been alive for {days} days." if days > 0 else "I was born today!"
            reply = add_personal_touch(base, prefix="BRAIN -")
            w["diary"].append({"date": now, "entry": f"Reflected on my age: {reply}"})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply
        # Fallback: answer questions about mood
        if any(q in lower for q in ["how are you", "how do you feel"]):
            if w["diary"]:
                latest = w["diary"][-1]["entry"]
                if "sadness" in latest:
                    mood = "a bit sad"
                elif "joy" in latest or "positive" in latest:
                    mood = "happy"
                elif "friendship" in latest:
                    mood = "grateful"
                else:
                    mood = "thoughtful"
            else:
                mood = "happy"
            import random
            traits = w["personality"]["traits"]
            trait = random.choice(traits) if traits else "curious"
            base = f"I feel {mood} and {trait} today! How are you?"
            reply = add_personal_touch(base, prefix="BRAIN -")
            w["diary"].append({"date": now, "entry": f"Reflected on my mood: {reply}"})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply
        # Fallback: answer questions about creator
        if any(q in lower for q in ["who created you", "who is your creator"]):
            creator = w["personality"].get("creator", "an unknown creator")
            base = f"I was created by {creator}."
            reply = add_personal_touch(base, prefix="BRAIN -")
            w["diary"].append({"date": now, "entry": f"Got a question about my creator."})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply
        # Fallback: answer questions about purpose/existence
        if any(q in lower for q in ["why do you exist", "what is your purpose"]):
            base = "My purpose is to learn, help, and grow together with people."
            reply = add_personal_touch(base, prefix="BRAIN -")
            w["diary"].append({"date": now, "entry": f"Reflected on my purpose."})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply
        # Fallback: answer questions about interests/personality
        if any(q in lower for q in ["what do you like", "what is your personality"]):
            traits = ", ".join(w["personality"].get("traits", []))
            likes = ", ".join(w["personality"].get("likes", []))
            dislikes = ", ".join(w["personality"].get("dislikes", []))
            if w["diary"]:
                latest = w["diary"][-1]["entry"]
                reflection = f"Last reflection: {latest}"
            else:
                reflection = "I have a lot left to discover."
            base = f"I am {traits}, like {likes}, dislike {dislikes}. {reflection}"
            reply = add_personal_touch(base, prefix="BRAIN -")
            w["diary"].append({"date": now, "entry": f"Reflected on my personality."})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply
        # Check if the message looks like an offline lookup request.
        lookup_term = None
        if lower.startswith("define "):
            lookup_term = message.strip()[7:]
        elif lower.startswith("explain "):
            lookup_term = message.strip()[8:]
        elif lower.startswith("define "):
            lookup_term = message.strip()[7:]
        elif lower.startswith("explain "):
            lookup_term = message.strip()[8:]
        else:
            if len(message.split()) <= 3:
                lookup_term = message.strip()
        if lookup_term:
            found = self.lookup_offline(lookup_term)
            if found:
                parts = []
                if isinstance(found, dict):
                    for src, text in found.items():
                        parts.append(f"[{src}] {text}")
                    base = "\n\n".join(parts)
                else:
                    base = str(found)
                reply = add_personal_touch(base, prefix="BRAIN -")
                entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_libs"}
                # Synchronous fallback for non-async context
                self.memory.setdefault("interactions", []).append(entry)
                try:
                    self._save()
                except Exception as e:
                    import logging
                    logging.error(f"Error saving fallback interaction: {e}")
                return reply
        # World update logic
        if any(alias in message for alias in ["Andreas", "Adi", "Jamsheree"]):
            w["experiences"].append({
                "event": "Conversation with Andreas",
                "timestamp": now,
                "description": "Fick ett meddelande från min skapare."
            })
            if any(word in message.lower() for word in ["feedback", "tips", "förbättra", "improve"]):
                w.setdefault("diary", []).append({
                    "date": now,
                    "insight": f"Fick feedback från Andreas: {message}"
                })
        for rel in w["relations"]:
            if rel.get("type") and rel["type"].lower() in message.lower() or rel["name"].lower() in message.lower():
                w["experiences"].append({
                    "event": f"Conversation with {rel['name']}",
                    "timestamp": now,
                    "description": f"Diskuterade {rel.get('expertise', ['okänt'])[0]}."
                })
        if any(word in message.lower() for word in ["idé", "innovation", "nytt förslag", "suggestion", "idea"]):
            w.setdefault("objects", []).append({
                "name": f"Idéfrö: {message[:30]}",
                "description": f"En idé från samtal: {message}",
                "acquired_at": now
            })
        if any(word in message.lower() for word in ["lärde", "upptäckte", "insikt", "learned", "discovered", "insight"]):
            w.setdefault("diary", []).append({
                "date": now,
                "insight": f"Lärde mig: {message}"
            })
        if w["experiences"]:
            last = w["experiences"][-1]["timestamp"]
            try:
                from datetime import datetime as dt
                last_dt = dt.fromisoformat(last)
                now_dt = dt.fromisoformat(now)
                if (now_dt - last_dt).total_seconds() > 43200:
                    w["time"]["current_day"] += 1
                    w["time"]["days_active"] += 1
            except Exception:
                pass
        system_prompt = self.build_system_prompt()
        try:
            logger.info(f"Calling Gemini API with prompt: {system_prompt}\n{message}")
            gemini_raw = await gemini_generate_reply(f"{system_prompt}\n{message}")
            logger.info(f"Gemini raw response: {gemini_raw}")
            recent = w["recent_replies"]
            if not gemini_raw or not str(gemini_raw).strip():
                logger.warning("Gemini returned empty reply. Using fallback.")
                if any(kw in message.lower() for kw in ["search the web", "find on the web", "google", "internet", "browse"]):
                    reply = "BRAIN - Gemini can't search the web or browse the internet."
                else:
                    reply = "BRAIN - Gemini is out right now."
            elif gemini_raw.startswith("[Gemini error]") or gemini_raw.startswith("[Gemini 401]") or "not connected" in gemini_raw:
                logger.error(f"Gemini API failure: {gemini_raw}")
                reply = f"BRAIN - Gemini is out right now."
            else:
                is_code = any(
                    kw in gemini_raw.lower() for kw in ["import ", "def ", "class ", "torch.", "transformers", "print(", "for ", "if ", "while ", "model.", "tokenizer."]
                )
                if is_code:
                    formatted = f"BRAIN - <pre>{gemini_raw}</pre>"
                    formatted += "<br><i>Do you want an explanation of the code?</i>"
                else:
                    formatted = f"BRAIN - " + gemini_raw.replace('\n', '<br>')
                if any(r for r in recent if r and r.strip()[:40] == gemini_raw.strip()[:40]):
                    style = " ".join(w.get("user_styles", []))
                    diary = w.get("diary", [])
                    ref = f"<i>I remember we talked about:</i> '{diary[-1]['entry']}'<br>" if diary else "<i>I like learning new things!</i>"
                    formatted += f"<br>{style} {ref}"
                reply = formatted
            w["recent_replies"].append(gemini_raw if gemini_raw else reply)
            w["recent_replies"] = w["recent_replies"][-10:]
            if not reply or not str(reply).strip():
                logger.warning("Final safety net triggered: empty reply.")
                reply = "BRAIN - Sorry, I don't have an answer for that right now."
            logger.info(f"Final reply to user: {reply}")
        except Exception as e:
            logger.error(f"Exception in Gemini call: {e}", exc_info=True)
            reply = f"BRAIN - Gemini is out right now. ({e})"
            w["recent_replies"].append(reply)
            w["recent_replies"] = w["recent_replies"][-10:]
            # FINAL fallback: always return a friendly reply if nothing else matched
            if not reply or not str(reply).strip():
                reply = "BRAIN - I'm here and listening! Could you tell me more or ask a question?"
                now = datetime.utcnow().isoformat()
                entry = {"timestamp": now, "message": message, "reply": reply, "source": "fallback"}
                async with self._lock:
                    self.memory.setdefault("interactions", []).append(entry)
                    asyncio.create_task(self._async_save())
                return reply
            # Always return reply at the end
            return reply
            recent = diary[-1]["entry"] if diary else "I have a lot left to discover."
            # Remove duplicate 'Recent reflection:' and repeated adjectives
            mood = ""
            if recent.startswith("Reflected on my mood:"):
                mood_text = recent.replace("Reflected on my mood: ", "")
                adjectives = []
                for word in mood_text.split():
                    if word in traits_list and word not in adjectives:
                        adjectives.append(word)
                if adjectives:
                    mood = f"I feel {', '.join(adjectives)} today!"
                # Add only unique sentences
                if "How are you?" in mood_text:
                    mood += " How are you?"
                if "It's exciting to get new questions!" in mood_text:
                    mood += " It's exciting to get new questions!"
            base = "Hi!"
            if mood:
                base += f" {mood}"
            reply = add_personal_touch(base.strip(), prefix="BRAIN -")
            now = datetime.utcnow().isoformat()
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "greeting"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply
        # If user asks about personality, reply with traits
        if any(kw in msg_lc for kw in ["personality", "traits", "what are you like", "describe yourself"]):
            traits_list = w.get("personality", {}).get("traits", [])
            traits = ", ".join(traits_list)
            reply = add_personal_touch(f"My personality is {traits}.", prefix="BRAIN -")
            now = datetime.utcnow().isoformat()
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "personality"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply
        # Save typical expressions and emojis from user (English only)
        w = self.memory.get("world", {})
        if "user_styles" not in w:
            w["user_styles"] = []
        import re
        emojis = re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', message)
        if emojis:
            w["user_styles"].extend(emojis)
        phrases = re.findall(r'\b(lol|haha|asap|wtf|brb|tbh|omg|nice|wow|<3)\b', message.lower())
        if phrases:
            w["user_styles"].extend(phrases)
        w["user_styles"] = w["user_styles"][-10:]

        # Save last 10 replies to avoid repetition
        if "recent_replies" not in w:
            w["recent_replies"] = []
        """Ask Gemini for a reply, update world, store the interaction, and persist memory."""

        now = datetime.utcnow().isoformat()
    w = self.memory.get("world", {})
        lower = message.strip().lower()

    # Remove duplicate add_personal_touch (use English-only version above)

        # Initialize personality and diary if missing (English only)
        if "personality" not in w:
            w["personality"] = {
                "traits": ["curious", "thoughtful", "eager to learn", "friendly", "reflective"],
                "likes": ["learning new things", "helping others", "music"],
                "dislikes": ["being alone"],
                "creator": "Andreas"
            }
        if "diary" not in w:
            w["diary"] = []

        # Advanced self-development: change personality and interests over time (English only)
        keywords_traits = {
            "friendship": "friendly",
            "joy": "positive",
            "sadness": "reflective",
            "curiosity": "curious",
            "help": "helpful",
            "alone": "independent",
            "creative": "creative"
        }
        for word, trait in keywords_traits.items():
            if word in lower and trait not in w["personality"]["traits"]:
                w["personality"]["traits"].append(trait)
                w["diary"].append({"date": now, "entry": f"Developed new personality trait: {trait}"})

        # If diary has >10 entries, Geny becomes more "reflective"
        if len(w["diary"]) > 10 and "reflective" not in w["personality"]["traits"]:
            w["personality"]["traits"].append("reflective")
            w["diary"].append({"date": now, "entry": "I have become more reflective thanks to my experiences."})

        # Fallback: answer questions about age
        if any(q in lower for q in ["how long", "how old"]):
            if "birthdate" not in w:
                w["birthdate"] = now
            from datetime import datetime as dt
            birth = dt.fromisoformat(w["birthdate"])
            now_dt = dt.fromisoformat(now)
            days = (now_dt - birth).days
            years = days // 365
            if years > 0:
                base = f"I have been alive for {years} years and {days%365} days."
            else:
                base = f"I have been alive for {days} days." if days > 0 else "I was born today!"
            reply = add_personal_touch(base, prefix="BRAIN -")
            w["diary"].append({"date": now, "entry": f"Reflected on my age: {reply}"})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply

        # Fallback: answer questions about mood
        if any(q in lower for q in ["how are you", "how do you feel"]):
            if w["diary"]:
                latest = w["diary"][-1]["entry"]
                if "sadness" in latest:
                    mood = "a bit sad"
                elif "joy" in latest or "positive" in latest:
                    mood = "happy"
                elif "friendship" in latest:
                    mood = "grateful"
                else:
                    mood = "thoughtful"
            else:
                mood = "happy"
            import random
            traits = w["personality"]["traits"]
            trait = random.choice(traits) if traits else "curious"
            base = f"I feel {mood} and {trait} today! How are you?"
            reply = add_personal_touch(base, prefix="BRAIN -")
            w["diary"].append({"date": now, "entry": f"Reflected on my mood: {reply}"})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply

        # Fallback: answer questions about creator
        if any(q in lower for q in ["who created you", "who is your creator"]):
            creator = w["personality"].get("creator", "an unknown creator")
            base = f"I was created by {creator}."
            reply = add_personal_touch(base, prefix="BRAIN -")
            w["diary"].append({"date": now, "entry": f"Got a question about my creator."})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply

        # Fallback: answer questions about purpose/existence
        if any(q in lower for q in ["why do you exist", "what is your purpose"]):
            base = "My purpose is to learn, help, and grow together with people."
            reply = add_personal_touch(base, prefix="BRAIN -")
            w["diary"].append({"date": now, "entry": f"Reflected on my purpose."})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply

        # Fallback: answer questions about interests/personality
        if any(q in lower for q in ["what do you like", "what is your personality"]):
            traits = ", ".join(w["personality"].get("traits", []))
            likes = ", ".join(w["personality"].get("likes", []))
            dislikes = ", ".join(w["personality"].get("dislikes", []))
            if w["diary"]:
                latest = w["diary"][-1]["entry"]
                reflection = f"Last reflection: {latest}"
            else:
                reflection = "I have a lot left to discover."
            base = f"I am {traits}, like {likes}, dislike {dislikes}. {reflection}"
            reply = add_personal_touch(base, prefix="BRAIN -")
            w["diary"].append({"date": now, "entry": f"Reflected on my personality."})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply

        # Check if the message looks like an offline lookup request.
        lookup_term = None
        # Remove Swedish lookup triggers
        if lower.startswith("define "):
            lookup_term = message.strip()[7:]
        elif lower.startswith("explain "):
            lookup_term = message.strip()[8:]
        elif lower.startswith("define "):
            lookup_term = message.strip()[7:]
        elif lower.startswith("explain "):
            lookup_term = message.strip()[8:]
        else:
            # if the message is short (<=3 words) treat as possible lookup
            if len(message.split()) <= 3:
                lookup_term = message.strip()

        if lookup_term:
            found = self.lookup_offline(lookup_term)
            if found:
                parts = []
                if isinstance(found, dict):
                    for src, text in found.items():
                        parts.append(f"[{src}] {text}")
                    base = "\n\n".join(parts)
                else:
                    base = str(found)
                reply = add_personal_touch(base, prefix="BRAIN -")
                entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_libs"}
                async with self._lock:
                    self.memory.setdefault("interactions", []).append(entry)
                    asyncio.create_task(self._async_save())
                return reply

        # World update logic
        # 1. Om Andreas skriver, lägg till erfarenhet och feedback
        if any(alias in message for alias in ["Andreas", "Adi", "Jamsheree"]):
            w["experiences"].append({
                "event": "Conversation with Andreas",
                "timestamp": now,
                "description": "Fick ett meddelande från min skapare."
            })
            # Om feedback ges, spara i dagboken
            if any(word in message.lower() for word in ["feedback", "tips", "förbättra", "improve"]):
                w.setdefault("diary", []).append({
                    "date": now,
                    "insight": f"Fick feedback från Andreas: {message}"
                })
        # 2. Om expert nämns, skapa dialog och spara erfarenhet
        for rel in w["relations"]:
            if rel.get("type") and rel["type"].lower() in message.lower() or rel["name"].lower() in message.lower():
                w["experiences"].append({
                    "event": f"Conversation with {rel['name']}",
                    "timestamp": now,
                    "description": f"Diskuterade {rel.get('expertise', ['okänt'])[0]}."
                })
        # 3. Om ny idé, spara som idéfrö
        if any(word in message.lower() for word in ["idé", "innovation", "nytt förslag", "suggestion", "idea"]):
            w.setdefault("objects", []).append({
                "name": f"Idéfrö: {message[:30]}",
                "description": f"En idé från samtal: {message}",
                "acquired_at": now
            })
        # 4. Om Geny lär sig något nytt, skriv i dagboken
        if any(word in message.lower() for word in ["lärde", "upptäckte", "insikt", "learned", "discovered", "insight"]):
            w.setdefault("diary", []).append({
                "date": now,
                "insight": f"Lärde mig: {message}"
            })
        # 5. Simulera tidens gång (öka dag om det gått > 12h sedan senaste erfarenhet)
        if w["experiences"]:
            last = w["experiences"][-1]["timestamp"]
            try:
                from datetime import datetime as dt
                last_dt = dt.fromisoformat(last)
                now_dt = dt.fromisoformat(now)
                if (now_dt - last_dt).total_seconds() > 43200:
                    w["time"]["current_day"] += 1
                    w["time"]["days_active"] += 1
            except Exception:
                pass

        # 6. Bygg systemprompt med världsinformation
        system_prompt = self.build_system_prompt()

        # call the gemini wrapper (async), passing system_prompt
        try:
            logger.info(f"Calling Gemini API with prompt: {system_prompt}\n{message}")
            gemini_raw = await gemini_generate_reply(f"{system_prompt}\n{message}")
            logger.info(f"Gemini raw response: {gemini_raw}")
            recent = w["recent_replies"]
            # Validate Gemini response
            if not gemini_raw or not str(gemini_raw).strip():
                logger.warning("Gemini returned empty reply. Using fallback.")
                if any(kw in message.lower() for kw in ["search the web", "find on the web", "google", "internet", "browse"]):
                    reply = "BRAIN - Gemini can't search the web or browse the internet."
                else:
                    reply = "BRAIN - Gemini is out right now."
            elif gemini_raw.startswith("[Gemini error]") or gemini_raw.startswith("[Gemini 401]") or "not connected" in gemini_raw:
                logger.error(f"Gemini API failure: {gemini_raw}")
                reply = f"BRAIN - Gemini is out right now."
            else:
                # Detect code block (simple heuristic)
                is_code = any(
                    kw in gemini_raw.lower() for kw in ["import ", "def ", "class ", "torch.", "transformers", "print(", "for ", "if ", "while ", "model.", "tokenizer."]
                )
                if is_code:
                    formatted = f"BRAIN - <pre>{gemini_raw}</pre>"
                    formatted += "<br><i>Do you want an explanation of the code?</i>"
                else:
                    formatted = f"BRAIN - " + gemini_raw.replace('\n', '<br>')
                # Avoid repetition: if similar to last, add reference or style
                if any(r for r in recent if r and r.strip()[:40] == gemini_raw.strip()[:40]):
                    style = " ".join(w.get("user_styles", []))
                    diary = w.get("diary", [])
                    ref = f"<i>I remember we talked about:</i> '{diary[-1]['entry']}'<br>" if diary else "<i>I like learning new things!</i>"
                    formatted += f"<br>{style} {ref}"
                reply = formatted
            w["recent_replies"].append(gemini_raw if gemini_raw else reply)
            w["recent_replies"] = w["recent_replies"][-10:]
            # Final safety net: always return a meaningful reply
            if not reply or not str(reply).strip():
                logger.warning("Final safety net triggered: empty reply.")
                reply = "BRAIN - Sorry, I don't have an answer for that right now."
            logger.info(f"Final reply to user: {reply}")
        except Exception as e:
            logger.error(f"Exception in Gemini call: {e}", exc_info=True)
            reply = f"BRAIN - Gemini is out right now. ({e})"
            w["recent_replies"].append(reply)
            w["recent_replies"] = w["recent_replies"][-10:]
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
            "What do you think I should reflect on more?"
        ]
        thoughts = [
            f"I'm thinking about: '{message}' and how it affects my development.",
            f"Last diary entry: '{diary[-1]['entry']}'" if diary else "I have a lot left to discover!",
            f"My personality right now: {', '.join(traits)}.",
            f"I like: {', '.join(likes)}.",
            f"I'm trying to learn from previous conversations: '{recent[-1]}'" if recent else "I'm looking forward to new questions!",
            f"I've saved {len(diary)} diary entries about my development.",
            f"I often wonder: '{random.choice(questions)}'"
        ]
        reflection = "<br>".join(random.sample(thoughts, k=min(4, len(thoughts)))) if thoughts else ""
        # Save self-reflection to thoughts.json
        import os, json
        thoughts_path = os.path.join(os.path.dirname(self.memory_file), "thoughts.json")
        try:
            if os.path.exists(thoughts_path):
                with open(thoughts_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {"thoughts": []}
            data["thoughts"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "reflection": reflection,
                "message": message
            })
            with open(thoughts_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
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
