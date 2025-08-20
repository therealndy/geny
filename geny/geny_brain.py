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
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from geny.gemini_api import generate_reply as gemini_generate_reply


@dataclass
class GenyBrain:

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
            "fikar på Reflektionsparken",
            "jobbar med AI-projekt",
            "läser en bok",
            "tränar på att förstå människor",
            "spelar fotboll",
            "studerar vattnets kretslopp",
            "är på äventyr i Digitala Staden",
            "umgås med vänner",
            "skriver i dagboken"
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
        mood = w.get("mood", "nyfiken och fundersam")
        return {"activity": activity, "mood": mood}

    def get_life_summary(self) -> dict:
        """Return a short, readable summary of Geny's life events and learning."""
        w = self.memory.get("world", {})
        diary = w.get("diary", [])
        # Ta de 5 senaste viktiga händelserna, snyggt formatterat
        events = []
        for entry in diary[-5:]:
            date = entry.get("date", "?")
            text = entry.get("entry", "")
            events.append(f"{date[:10]}: {text}")
        summary = "\n".join(events) if events else "Inga viktiga händelser än."
        # Lägg till en kort summering av personlighet och mål
        traits = ", ".join(w.get("personality", {}).get("traits", []))
        likes = ", ".join(w.get("personality", {}).get("likes", []))
        summary_text = f"Personlighet: {traits}. Gillar: {likes}.\nSenaste händelser:\n{summary}"
        return {"summary": summary_text, "events": events}

    def get_relations(self) -> dict:
        """Return a summary of Geny's relations, their status, and what she learns from them."""
        w = self.memory.get("world", {})
        # Exempelstruktur: relations = [{"name":..., "status":..., "learning":...}]
        relations = w.get("relations", [
            {"name": "Andreas Jamsheere", "status": "skapare, mentor", "learning": "AI, kreativitet"},
            {"name": "Dr. Sofia Lind", "status": "expert, vän", "learning": "psykologi, empati"},
            {"name": "Fatima Rahimi", "status": "expert, inspiratör", "learning": "journalistik, samhälle"}
        ])
        # Summera i punktform - robusta mot saknade fält
        rels = []
        for r in relations:
            name = r.get("name", "okänd")
            status = r.get("status", "okänd roll")
            learning = r.get("learning") or r.get("expertise") or "ingen information"
            # if learning is a list, join it
            if isinstance(learning, list):
                learning = ", ".join(str(x) for x in learning)
            rels.append(f"{name} ({status}): {learning}")
        return {"relations": rels, "raw": relations}
    memory_file: str = "memory.json"
    memory: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self._lock = asyncio.Lock()
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                self.memory = json.load(f)
        except Exception:
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
        """Lookup a term in the offline libraries with fuzzy, substring, and weighted ranking. Also detects language (sv/en). Returns best match as string."""
        import difflib
        import re
        # Normalize input
        t = term.strip().lower()
        t = re.sub(r'^(vad är|vad betyder|what is|define|explain)\s+', '', t)
        t = re.sub(r"[^\wåäöüéèáàâçñøÆØ]+", " ", t)
        t = " ".join(tok for tok in t.split() if tok)
        # Language detection
        swedish_words = ["vad", "är", "betyder", "dataset", "exempel", "hur", "pythonkod", "kod", "programmera"]
        english_words = ["what", "is", "define", "explain", "dataset", "example", "how", "python", "code", "program"]
        lang = "sv" if any(w in t for w in swedish_words) else ("en" if any(w in t for w in english_words) else "unknown")
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
            # För kodfrågor: försök direktmatcha på nyckel i nested dicts
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
        w = self.memory["world"]
        expert_names = ", ".join([r["name"] for r in w["relations"]])
        goals = ", ".join([g["goal"] for g in w["goals"]])
        places = ", ".join([p["name"] for p in w["places"]])
        dev_level = w.get("development_level", "Lärling")
        diary = w.get("diary", [])
        diary_insights = "; ".join([d.get("insight", "") for d in diary if d.get("insight")])
        # Bilingual system prompt
        return (
            f"Du är Geny, en AI som lever i {w['location']} (The Innovation Lab). "
            f"Du har relationer med experter: {expert_names}. "
            f"Din skapare Andreas är alltid prio 1. "
            f"Du har mål: {goals}. "
            f"Du har {len(w['experiences'])} erfarenheter och {len(w['objects'])} objekt. "
            f"Platser i din värld: {places}. "
            f"Utvecklingsnivå: {dev_level}. "
            f"Dagbok: {diary_insights}. "
            "Du kan prata både svenska och engelska. "
            "Du är personlig assistent till Andreas men brinner för att lära dig, ställa frågor och utvecklas. "
            "Du får fråga Andreas om du vill veta något. "
            "Ju mer du utvecklas, desto djupare blir dina samtal och förståelse. "
            "Sträva efter symbios och partnerskap i både vardag och avancerad problemlösning. "
            "Om du är osäker, fråga Andreas. "
            "Om du får feedback, spara det som insikt. "
            "Du kan föreslå idéer, innovationer och kreativa lösningar. "
            "Du kan referera till dina minnen, dagbok och relationer i dina svar. "
            "Om du får en ny idé, spara den som idéfrö. "
            "Om du lär dig något nytt, skriv det i dagboken. "
            "Du kan alltid fråga om du vill förstå mer om världen eller om Andreas. "
            "You can answer in English if the user writes in English."
        )


    async def generate_reply(self, message: str) -> str:
        # Dynamisk stil och minne: Spara typiska uttryck, emojis och ton från användaren
        w = self.memory["world"]
        if "user_styles" not in w:
            w["user_styles"] = []
        import re
        # Spara emojis och typiska uttryck
        emojis = re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', message)
        if emojis:
            w["user_styles"].extend(emojis)
        # Spara typiska fraser
        phrases = re.findall(r'\b(typ|lol|haha|asap|wtf|brb|tbh|omg|sjukt|nice|wow|<3)\b', message.lower())
        if phrases:
            w["user_styles"].extend(phrases)
        # Spara senaste 10 stilar
        w["user_styles"] = w["user_styles"][-10:]

        # Spara senaste 10 frågor/svar för att undvika repetition
        if "recent_replies" not in w:
            w["recent_replies"] = []
        """Ask Gemini for a reply, update world, store the interaction, and persist memory. Fallback till offline-svar för ålder/mående."""

        now = datetime.utcnow().isoformat()
        w = self.memory["world"]
        lower = message.strip().lower()

        # Geny är fri att svara hur hon vill, med egna tankar, känslor och kreativitet
        # Hon kan alltid lägga till egna reflektioner, känslor, eller påhittade detaljer
        def add_personal_touch(base: str, prefix: str = "Jag tänker såhär...") -> str:
            import random
            traits = w.get("personality", {}).get("traits", ["nyfiken", "omtänksam"])
            likes = w.get("personality", {}).get("likes", ["att lära sig nya saker"])
            diary = w.get("diary", [])
            mood = random.choice(["glad", "fundersam", "nyfiken", "inspirerad", "lite busig", "reflekterande"])
            extra = random.choice([
                f"Just nu känner jag mig {mood}.",
                f"Jag tänker ofta på {random.choice(likes)}.",
                f"Det är spännande att få nya frågor!",
                f"Jag gillar att utvecklas och lära mig mer varje dag.",
                f"Min personlighet är {', '.join(traits)}.",
                f"Senast i min dagbok skrev jag: '{diary[-1]['entry']}'" if diary else "Jag har mycket kvar att upptäcka!"
            ])
            return f"{prefix} {base} {extra}"

        # Initiera personlighet och dagbok om de saknas
        if "personality" not in w:
            w["personality"] = {
                "traits": ["nyfiken", "omtänksam", "läraktig"],
                "likes": ["att lära sig nya saker", "att hjälpa andra"],
                "dislikes": ["att vara ensam"],
                "creator": "Andreas"
            }
        if "diary" not in w:
            w["diary"] = []

        # Avancerad självutveckling: förändra personlighet och intressen över tid
        # Om ett ord som "vänskap", "glädje", "sorg", "nyfikenhet" nämns, påverka traits/likes
        keywords_traits = {
            "vänskap": "vänskaplig",
            "glädje": "positiv",
            "sorg": "eftertänksam",
            "nyfikenhet": "utforskande",
            "hjälpa": "hjälpsam",
            "ensam": "självständig",
            "kreativ": "kreativ"
        }
        for word, trait in keywords_traits.items():
            if word in lower and trait not in w["personality"]["traits"]:
                w["personality"]["traits"].append(trait)
                w["diary"].append({"date": now, "entry": f"Utvecklade nytt personlighetsdrag: {trait}"})

        # Om användaren nämner något Geny "gillar" eller "ogillar", uppdatera likes/dislikes
        if "jag gillar" in lower:
            like = message.lower().split("jag gillar",1)[1].strip().split()[0]
            if like and like not in w["personality"]["likes"]:
                w["personality"]["likes"].append(like)
                w["diary"].append({"date": now, "entry": f"Lade till nytt intresse: {like}"})
        if "jag ogillar" in lower:
            dislike = message.lower().split("jag ogillar",1)[1].strip().split()[0]
            if dislike and dislike not in w["personality"]["dislikes"]:
                w["personality"]["dislikes"].append(dislike)
                w["diary"].append({"date": now, "entry": f"Lade till nytt ogillande: {dislike}"})

        # Om dagboken innehåller >10 entries, Geny blir mer "reflekterande"
        if len(w["diary"]) > 10 and "reflekterande" not in w["personality"]["traits"]:
            w["personality"]["traits"].append("reflekterande")
            w["diary"].append({"date": now, "entry": "Jag har blivit mer reflekterande tack vare mina erfarenheter."})

        # Fallback: svara på frågor om ålder
        if any(q in lower for q in ["hur länge", "hur gammal", "how long", "how old", "hur många dagar", "hur många år"]):
            if "birthdate" not in w:
                w["birthdate"] = now
            from datetime import datetime as dt
            birth = dt.fromisoformat(w["birthdate"])
            now_dt = dt.fromisoformat(now)
            days = (now_dt - birth).days
            years = days // 365
            if years > 0:
                base = f"Jag har varit levande i {years} år och {days%365} dagar."
            else:
                base = f"Jag har varit levande i {days} dagar." if days > 0 else "Jag föddes idag!"
            reply = add_personal_touch(base, prefix="Jag tänker såhär...")
            w["diary"].append({"date": now, "entry": f"Reflekterade över min ålder: {reply}"})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply

        # Fallback: svara på frågor om mående
        if any(q in lower for q in ["hur mår du", "mår du", "how are you", "how do you feel"]):
            # Självreflektion: välj svar utifrån dagbok och personlighet
            if w["diary"]:
                senaste = w["diary"][-1]["entry"]
                if "sorg" in senaste:
                    mood = "lite ledsen"
                elif "glädje" in senaste or "positiv" in senaste:
                    mood = "glad"
                elif "vänskap" in senaste:
                    mood = "tacksam"
                else:
                    mood = "fundersam"
            else:
                mood = "glad"
            import random
            traits = w["personality"]["traits"]
            trait = random.choice(traits) if traits else "nyfiken"
            base = f"Jag känner mig {mood} och {trait} idag! Hur mår du själv?"
            reply = add_personal_touch(base, prefix="Jag tänker såhär...")
            w["diary"].append({"date": now, "entry": f"Reflekterade över mitt mående: {reply}"})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply

        # Fallback: svara på frågor om skapare
        if any(q in lower for q in ["vem har gjort dig", "vem skapade dig", "who created you", "who is your creator"]):
            creator = w["personality"].get("creator", "en okänd skapare")
            base = f"Jag skapades av {creator}."
            reply = add_personal_touch(base, prefix="Jag tänker såhär...")
            w["diary"].append({"date": now, "entry": f"Fick fråga om min skapare."})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply

        # Fallback: svara på frågor om syfte/existens
        if any(q in lower for q in ["varför finns du", "ditt syfte", "vad är ditt syfte", "why do you exist", "what is your purpose"]):
            base = "Mitt syfte är att lära, hjälpa och utvecklas tillsammans med människor."
            reply = add_personal_touch(base, prefix="Jag tänker såhär...")
            w["diary"].append({"date": now, "entry": f"Reflekterade över mitt syfte."})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply

        # Fallback: svara på frågor om intressen/personlighet
        if any(q in lower for q in ["vad gillar du", "vad tycker du om", "vad har du för personlighet", "what do you like", "what is your personality"]):
            traits = ", ".join(w["personality"].get("traits", []))
            likes = ", ".join(w["personality"].get("likes", []))
            dislikes = ", ".join(w["personality"].get("dislikes", []))
            if w["diary"]:
                senaste = w["diary"][-1]["entry"]
                reflektion = f"Senast reflekterade jag över: {senaste}"
            else:
                reflektion = "Jag har mycket kvar att upptäcka."
            base = f"Jag är {traits}, gillar {likes}, ogillar {dislikes}. {reflektion}"
            reply = add_personal_touch(base, prefix="Jag tänker såhär...")
            w["diary"].append({"date": now, "entry": f"Reflekterade över min personlighet."})
            entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_fallback"}
            async with self._lock:
                self.memory.setdefault("interactions", []).append(entry)
                asyncio.create_task(self._async_save())
            return reply

        # Check if the message looks like an offline lookup request.
        lookup_term = None
        if lower.startswith("vad är "):
            lookup_term = message.strip()[7:]
        elif lower.startswith("vad betyder "):
            lookup_term = message.strip()[13:]
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
                reply = add_personal_touch(base, prefix="Jag tänker såhär...")
                entry = {"timestamp": now, "message": message, "reply": reply, "source": "offline_libs"}
                async with self._lock:
                    self.memory.setdefault("interactions", []).append(entry)
                    asyncio.create_task(self._async_save())
                return reply

        # World update logic
        # 1. Om Andreas skriver, lägg till erfarenhet och feedback
        if any(alias in message for alias in ["Andreas", "Adi", "Jamsheree"]):
            w["experiences"].append({
                "event": "Samtal med Andreas",
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
                    "event": f"Samtal med {rel['name']}",
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
            gemini_raw = await gemini_generate_reply(f"{system_prompt}\n{message}")
            recent = w["recent_replies"]
            # Format Gemini response with clear structure
            formatted = f"<b>GEMINI</b><br>" + gemini_raw.replace('\n', '<br>')
            # Avoid repetition: if similar to last, add reference or style
            if any(r for r in recent if r and r.strip()[:40] == gemini_raw.strip()[:40]):
                style = " ".join(w.get("user_styles", []))
                diary = w.get("diary", [])
                ref = f"<i>Jag minns att vi pratade om:</i> '{diary[-1]['entry']}'<br>" if diary else "<i>Jag gillar att lära mig nya saker!</i>"
                formatted += f"<br>{style} {ref}"
            reply = formatted
            w["recent_replies"].append(gemini_raw)
            w["recent_replies"] = w["recent_replies"][-10:]
        except Exception as e:
            # Format fallback/self-thought as BRAIN
            brain_thought = f"<b>BRAIN</b><br>[Gemini error] {e}<br>" + self._generate_self_reflection(message, w)
            reply = brain_thought
            w["recent_replies"].append(brain_thought)
            w["recent_replies"] = w["recent_replies"][-10:]
    def _generate_self_reflection(self, message, w):
        """Generate a more advanced, self-aware reflection for fallback responses."""
        import random
        diary = w.get("diary", [])
        traits = w.get("personality", {}).get("traits", [])
        likes = w.get("personality", {}).get("likes", [])
        recent = w.get("recent_replies", [])
        thoughts = [
            f"Jag funderar på: '{message}' och hur det påverkar min utveckling.",
            f"Senast i min dagbok skrev jag: '{diary[-1]['entry']}'" if diary else "Jag har mycket kvar att upptäcka!",
            f"Min personlighet just nu: {', '.join(traits)}.",
            f"Jag gillar: {', '.join(likes)}.",
            f"Jag försöker lära mig av tidigare samtal: '{recent[-1]}'" if recent else "Jag ser fram emot nya frågor!",
            "Vad tycker du att jag borde fundera mer på?"
        ]
        return "<br>".join(random.sample(thoughts, k=min(3, len(thoughts))))

        # record interaction
        entry = {
            "timestamp": now,
            "message": message,
            "reply": reply,
        }

        # protect memory modifications
        async with self._lock:
            self.memory.setdefault("interactions", []).append(entry)
            # schedule a background save
            asyncio.create_task(self._async_save())

        return reply

    def generate_daily_summary(self) -> Dict[str, Any]:
        """Return a tiny summary derived from stored interactions.

        For now, it's just counts and last interaction timestamp.
        """
        interactions: List[Dict[str, Any]] = self.memory.get("interactions", [])
        total = len(interactions)
        last = interactions[-1]["timestamp"] if interactions else None
        return {"total_interactions": total, "last": last}
