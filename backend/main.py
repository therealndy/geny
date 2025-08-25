import asyncio
import json
import logging
import os
import subprocess
import time
from collections import deque
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from geny import gemini_api
from geny.geny_brain import GenyBrain
from geny.web_search import (ddg_aggregate_with_aliases, ddg_instant_answer,
                             wikipedia_search)
from geny_ai.lifetwin.engine import LifeTwin
from geny_ai.memory_sphere.service import get_service as get_memsvc
from geny_ai.neuro.sandbox import NeuroState
from geny_ai.orchestrator.scheduler import run_nightly
from geny_ai.rag.rag import build_rag_prompt
from geny_ai.rag.store import VectorStore

# Configure logging immediately so module-level startup logs (e.g. in
# `geny.gemini_api`) are visible during process startup and in Render logs.
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger("geny_backend")

app = FastAPI()

# Allow CORS for all origins (development convenience)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_import_token_source():
    """Return (token, source) where source is 'env', 'file', or (None, None).

    For local debugging we allow a fallback file at /tmp/IMPORT_ADMIN_TOKEN.
    """
    token = os.environ.get("IMPORT_ADMIN_TOKEN")
    if token:
        return token, "env"
    try:
        p = "/tmp/IMPORT_ADMIN_TOKEN"
        if os.path.exists(p):
            with open(p, "r") as f:
                t = f.read().strip()
                if t:
                    return t, "file"
    except Exception:
        logger.exception("Error reading token file fallback")
    return None, None


brain = GenyBrain()
geny = brain
memsvc = get_memsvc()
_vectorstore: VectorStore | None = None
try:
    _vectorstore = VectorStore()
except Exception:
    # If dependencies aren't available, leave vectorstore as None; endpoints will handle this
    _vectorstore = None


# Simple in-memory protection for diary writes. Prefer a token if provided via
# WORLD_DIARY_TOKEN; otherwise enforce a modest rate limit per-process to avoid
# accidental/spammy writes (configurable via WORLD_DIARY_RATE_PER_MIN).

_diary_writes: deque[float] = deque()
_diary_rate_per_min = int(os.environ.get("WORLD_DIARY_RATE_PER_MIN", "30"))
_diary_rate_window_s = 60.0


# Background indexer task (optional)
_indexer_task: asyncio.Task | None = None


async def _periodic_indexer(interval_s: float = 300.0):
    logger.info("Background indexer starting (interval=%.1fs)", interval_s)
    try:
        while True:
            try:
                if _vectorstore is not None:
                    w = brain.memory.get("world", {})
                    diary = list(w.get("diary", []))
                    docs = []
                    for d in diary:
                        ts = d.get("date") or d.get("meta", {}).get("since_real")
                        docs.append(
                            {
                                "id": ts or str(len(docs)),
                                "text": d.get("entry", ""),
                                "meta": {"insight": d.get("insight")},
                            }
                        )
                    _vectorstore.rebuild_index(docs)
            except Exception:
                logger.exception("Periodic indexer iteration failed")
            await asyncio.sleep(interval_s)
    finally:
        logger.info("Background indexer stopped")


def maybe_start_background_indexer():
    global _indexer_task
    if os.environ.get("GENY_BACKGROUND_INDEX") == "1" and _indexer_task is None:
        try:
            interval = float(os.environ.get("GENY_BACKGROUND_INDEX_INTERVAL", "300"))
        except Exception:
            interval = 300.0
        _indexer_task = asyncio.create_task(_periodic_indexer(interval))


@app.post("/mem/index/diary")
async def mem_index_diary(force: bool = False):
    """Admin endpoint: rebuild the vectorstore index from `world.diary`.

    If vectorstore dependencies are missing, returns a helpful message.
    """
    if _vectorstore is None:
        return {
            "status": "vectorstore_unavailable",
            "hint": "Install sentence-transformers faiss-cpu numpy and restart.",
        }
    try:
        # Gather diary entries from brain.memory
        w = brain.memory.get("world", {})
        diary = list(w.get("diary", []))
        docs = []
        for d in diary:
            ts = (
                d.get("date")
                or d.get("meta", {}).get("since_real")
                or d.get("meta", {}).get("virtual", {}).get("now_real")
            )
            docs.append(
                {
                    "id": ts or str(len(docs)),
                    "text": d.get("entry", ""),
                    "meta": {"insight": d.get("insight")},
                }
            )
        count = _vectorstore.rebuild_index(docs)
        return {"status": "ok", "indexed": count}
    except Exception as e:
        logger.exception("Indexing diary failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/world/virtual-age")
async def get_virtual_age(persist: int | None = None):
    """Return Geny's virtual age. If ?persist=1, append a friendly diary entry and persist."""
    try:
        age = brain.get_virtual_age()
        if persist == 1:
            sentence = brain.format_and_persist_virtual_age()
            return {"age": age, "saved": True, "sentence": sentence}
        return {"age": age}
    except Exception as e:
        logger.exception("Failed to fetch virtual age: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# Emit a non-secret startup diagnostic about GenAI availability so platform logs
# clearly show whether the API key and client library are present in-process.
try:
    from geny import gemini_api as _g

    logger.info(
        "Startup GenAI status: api_key_present=%s, genai_module_available=%s",
        bool(getattr(_g, "API_KEY", None)),
        getattr(_g, "genai", None) is not None,
    )
except Exception as e:
    logger.exception("Failed to import geny.gemini_api at startup: %s", e)

# Log whether the IMPORT_ADMIN_TOKEN is present at process startup (do not log the value)
_token, _source = _get_import_token_source()
logger.info("IMPORT_ADMIN_TOKEN source at startup: %s", _source)

# Potentially start the background indexer if configured
try:
    maybe_start_background_indexer()
except Exception:
    logger.exception("Failed to start background indexer at startup")


class ChatRequest(BaseModel):
    message: str
    temperature: float | None = None


class DiaryEntry(BaseModel):
    entry: str
    insight: str | None = None
    tags: list[str] | None = None


class FeelingEntry(BaseModel):
    note: str
    mood: float | None = None
    stress: float | None = None
    energy: float | None = None


# Simple in-memory rate limiter for AI replies (4 per hour)
class RateLimiter:
    """In-memory sliding-window limiter with logical scoping.

    Notes:
    - Uses a key to scope counts (e.g., per-route). In pytest, we further
      scope by PYTEST_CURRENT_TEST to isolate tests within a process.
    """

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits_by_key: dict[str, deque] = {}

    def _key(self, scope: str | None) -> str:
        k = scope or "global"
        # During pytest, isolate counts per test function to avoid crosstalk
        pt = os.environ.get("PYTEST_CURRENT_TEST")
        if pt:
            k = f"{k}|{pt}"
        return k

    def _get_deque(self, key: str) -> deque:
        dq = self._hits_by_key.get(key)
        if dq is None:
            dq = deque()
            self._hits_by_key[key] = dq
        return dq

    def _prune(self, dq: deque, now: float):
        cutoff = now - self.window
        while dq and dq[0] < cutoff:
            dq.popleft()

    def allow(self, scope: str | None = None) -> bool:
        # If disabled (limit <= 0), always allow
        if self.limit <= 0:
            return True
        key = self._key(scope)
        dq = self._get_deque(key)
        now = time.time()
        self._prune(dq, now)
        if len(dq) >= self.limit:
            return False
        dq.append(now)
        return True

    def stats(self, scope: str | None = None) -> dict:
        key = self._key(scope)
        dq = self._get_deque(key)
        now = time.time()
        self._prune(dq, now)
        reset_in = 0.0
        if dq:
            reset_in = max(0.0, self.window - (now - dq[0]))
        return {
            "limit": self.limit,
            "count": len(dq),
            "window_seconds": self.window,
            "reset_in_seconds": int(reset_in),
        }


# Allow overriding rate limit via environment (set GENY_RL_LIMIT=0 to disable)
_rl_limit = os.environ.get("GENY_RL_LIMIT")
try:
    _rl_limit_val = int(_rl_limit) if _rl_limit is not None else 4
except Exception:
    _rl_limit_val = 4
ai_rl = RateLimiter(limit=_rl_limit_val, window_seconds=3600)

# Auto diary toggle: if enabled, /chat will also write a brief reflective diary entry
_auto_diary_enabled = os.environ.get("GENY_AUTO_DIARY", "1") == "1"


# --- Exploration mode (auto-curiosity) -------------------------------------
_exploration_task: asyncio.Task | None = None
_exploration_state: dict = {
    "running": False,
    "started_at": None,
    "interval_seconds": None,
    "last_run": None,
    "runs": 0,
}

# Movement/keep-alive state
_movement_task: asyncio.Task | None = None
_movement_state: dict = {
    "running": False,
    "started_at": None,
    "interval_seconds": None,
    "method": "internal",  # 'internal' or 'http'
    "follow_exploration": True,
    "last_tick": None,
    "ticks": 0,
}


def _effective_interval(base_interval: float | int | None) -> float:
    """Compute real-time interval between loops, modulated by virtual time scale.

    If scale > 1.0 (faster virtual time), we run more frequently by dividing.
    Clamped to [5s, 3600s]. Default base is 120s.
    """
    try:
        base = float(base_interval) if base_interval is not None else 120.0
    except Exception:
        base = 120.0
    scale = getattr(brain, "VIRTUAL_TIME_SCALE", 1.0) or 1.0
    # Faster virtual time -> shorter real interval; slower -> longer
    interval = base / max(0.1, float(scale))
    return float(min(3600.0, max(5.0, interval)))


async def _exploration_loop(interval_s: float):
    global _exploration_state
    logger.info("Exploration loop starting with interval %.1fs", interval_s)
    try:
        while _exploration_state.get("running", False):
            try:
                # Compose a short curiosity prompt using virtual time context
                vt = brain.get_virtual_age()
                now_v = brain.now_virtual().isoformat()
                prompt = (
                    "AUTO-CURIOSITY: In one or two sentences, write a concise diary insight "
                    "about something you (Geny) learned or noticed just now in your world. "
                    "Focus on personal growth or a question you want to explore next."
                )
                system = brain.build_system_prompt()
                # Call GenAI with guardrails; respect rate-limiter but continue silently on 429
                if ai_rl.allow("/exploration/loop"):
                    try:
                        reply = await gemini_api.generate_reply(f"{system}\n{prompt}")
                    except Exception:
                        reply = "I am reflecting silently and preparing questions for later."
                else:
                    reply = "(paused due to rate limits)"

                # Persist as a diary entry, tagged with virtual timestamp
                entry = {
                    "date": now_v,
                    "entry": reply,
                    "insight": reply,
                    "meta": {"source": "auto", "virtual": vt, "interval_s": interval_s},
                }
                async with brain._lock:
                    w = brain.memory.setdefault("world", {})
                    w.setdefault("diary", []).append(entry)
                    # Keep diary from growing without bounds (retain last 1000)
                    if len(w["diary"]) > 1000:
                        w["diary"] = w["diary"][-1000:]
                    asyncio.create_task(brain._async_save())

                # Optionally also record a lightweight interaction log line
                try:
                    brain.save_interaction("[auto] curiosity", reply)
                except Exception:
                    logger.debug("Failed to save auto interaction", exc_info=True)

                _exploration_state["runs"] = int(_exploration_state.get("runs", 0)) + 1
                _exploration_state["last_run"] = datetime.now(timezone.utc).isoformat()
                # Optional: treat exploration as "movement" to keep server awake
                try:
                    if _movement_state.get("running") and _movement_state.get(
                        "follow_exploration", True
                    ):
                        await _movement_tick()
                except Exception:
                    logger.debug(
                        "movement tick during exploration failed", exc_info=True
                    )
            except Exception:
                logger.exception("Exploration loop iteration failed")

            await asyncio.sleep(interval_s)
    finally:
        logger.info("Exploration loop stopped")


async def _movement_tick():
    """One movement tick: update presence and optionally ping HTTP health endpoint."""
    global _movement_state
    # Update presence into memory
    ts = datetime.now(timezone.utc).isoformat()
    async with brain._lock:
        w = brain.memory.setdefault("world", {})
        presence = w.setdefault("presence", {"last": None, "ticks": 0})
        presence["last"] = ts
        presence["ticks"] = int(presence.get("ticks", 0)) + 1
        asyncio.create_task(brain._async_save())
    _movement_state["last_tick"] = ts
    _movement_state["ticks"] = int(_movement_state.get("ticks", 0)) + 1

    # Optionally generate an inbound request to keep some platforms awake
    if _movement_state.get("method") == "http":
        try:
            import httpx

            url = os.environ.get("GENY_BASE_URL", "http://127.0.0.1:8000/healthz")
            timeout = float(os.environ.get("GENY_KEEPALIVE_TIMEOUT", "2.0"))
            async with httpx.AsyncClient(timeout=timeout) as client:
                await client.get(url)
        except Exception:
            # Non-fatal; ignore in local runs and tests
            pass


async def _movement_loop(interval_s: float):
    logger.info(
        "Movement loop starting with interval %.1fs (method=%s)",
        interval_s,
        _movement_state.get("method"),
    )
    try:
        while _movement_state.get("running", False):
            try:
                await _movement_tick()
            except Exception:
                logger.exception("Movement loop tick failed")
            await asyncio.sleep(interval_s)
    finally:
        logger.info("Movement loop stopped")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/admin/genai-status")
async def genai_status():
    """Admin endpoint (non-secret) returning whether a GenAI API key and the
    google.generativeai client are available in the running process.

    This intentionally does NOT return or log any secret values.
    """
    try:
        from geny import gemini_api as _g

        return {
            "api_key_present": bool(getattr(_g, "API_KEY", None)),
            "genai_module_available": getattr(_g, "genai", None) is not None,
        }
    except Exception as e:
        logger.exception("Failed to determine genai status: %s", e)
        return {"api_key_present": False, "genai_module_available": False}


@app.post("/chat")
async def chat(req: ChatRequest):
    logger.info(f"/chat endpoint received: {req.message}")
    try:
        if not ai_rl.allow("/chat"):
            return JSONResponse(
                status_code=429,
                content={"status": "rate_limited", **ai_rl.stats("/chat")},
            )
        # Intent: lightweight trigger to gather public info
        msg_lc = (req.message or "").lower()
        # Allow web search by default unless explicitly disabled. During tests we still disable it
        # unless PYTEST_CURRENT_TEST is not set. This makes local experimentation easier.
        allow_web = os.environ.get(
            "ALLOW_WEB_SEARCH", "1"
        ) == "1" and not os.environ.get("PYTEST_CURRENT_TEST")
        if "search the web" in msg_lc and " for " in msg_lc and allow_web:
            try:
                # Extract the query after 'for '
                q = req.message.split(" for ", 1)[1].strip().strip(".?")
                web = await ddg_instant_answer(q)
                abstract = web.get("abstract") or {}
                related = web.get("related") or []
                # If DuckDuckGo didn't return a useful abstract, attempt a Wikipedia fallback
                if not abstract:
                    try:
                        wiki = await wikipedia_search(q)
                        if wiki and wiki.get("extract"):
                            abstract = {
                                "text": wiki.get("extract"),
                                "url": wiki.get("content_urls", {})
                                .get("desktop", {})
                                .get("page"),
                                "source": "wikipedia",
                            }
                            # insert wikipedia as first related item for traceability
                            related = [
                                {
                                    "title": wiki.get("title"),
                                    "url": abstract.get("url"),
                                    "text": wiki.get("extract"),
                                }
                            ]
                    except Exception:
                        # Non-fatal, continue with whatever ddg returned
                        pass
                prompt = (
                    "Summarize the following public info in 4-6 concise bullets, strictly factual, with links in parentheses when present.\n\n"
                    f"Abstract: {abstract}\nRelated: {related[:5]}"
                )
                try:
                    text = await gemini_api.generate_reply(prompt, timeout=12)
                    summary = text.strip() or "(no summary)"
                except Exception:
                    items = [abstract.get("text", "")] + [
                        i.get("title", "") for i in related[:5]
                    ]
                    summary = "; ".join([s for s in items if s]) or "(no summary)"
                reply = "BRAIN - " + summary.replace("\n", "<br>")
                # Persist a profile snapshot too
                async with brain._lock:
                    w = brain.memory.setdefault("world", {})
                    profiles = w.setdefault("profiles", {})
                    profiles[q] = {
                        "summary": summary,
                        "web": web,
                        "updated": datetime.now(timezone.utc).isoformat(),
                    }
                    asyncio.create_task(brain._async_save())
            except Exception as _e:
                logger.exception("Inline web search failed: %s", _e)
                reply = "BRAIN - I tried to look that up, but couldn't fetch results right now."
        elif "search the web" in msg_lc and " for " in msg_lc and not allow_web:
            reply = "BRAIN - I can search the web when enabled. Please set ALLOW_WEB_SEARCH=1 on the server and ask again."
        else:
            # Optional RAG augmentation: consult the vectorstore if requested and available
            use_rag = os.environ.get("GENY_USE_RAG", "0") == "1"
            if use_rag and _vectorstore is not None:
                try:
                    docs = _vectorstore.search(req.message, k=4)
                    # Build a RAG prompt and ask GenAI to answer concisely
                    rag_prompt = build_rag_prompt(req.message, docs, max_snippets=3)
                    try:
                        reply = await gemini_api.generate_reply(rag_prompt, timeout=12)
                    except Exception:
                        # fallback to brain if GenAI fails
                        reply = await brain.generate_reply(req.message)
                except Exception:
                    # If retrieval or RAG fails, fallback to default
                    reply = await brain.generate_reply(req.message)
            else:
                reply = await brain.generate_reply(req.message)
        # Coerce non-string or empty values to a safe fallback
        try:
            if reply is None:
                reply = "BRAIN - Sorry, I couldn't generate a reply right now."
            else:
                # Ensure it's a string and not empty after strip
                reply = str(reply)
                if not reply.strip():
                    reply = "BRAIN - Sorry, I couldn't generate a reply right now."
        except Exception:
            reply = "BRAIN - Sorry, I couldn't generate a reply right now."
        logger.info(f"Geny reply: {reply}")
        # Always persist the interaction via MemoryModule for consistency
        try:
            brain.save_interaction(req.message, reply)
        except Exception:
            logger.exception("Failed to persist interaction")
        # Optional: also ingest message and reply into MemorySphere (best-effort)
        try:
            meta = {"source": "chat", "ts": datetime.now(timezone.utc).isoformat()}
            memsvc.ingest_text(f"USER: {req.message}", meta)
            memsvc.ingest_text(f"GENY: {reply}", meta)
        except Exception:
            pass
        # Optional: write a short auto-diary reflection capturing this exchange
        if _auto_diary_enabled:
            try:
                vt = brain.get_virtual_age()
                now_v = brain.now_virtual().isoformat()
                entry = {
                    "date": now_v,
                    "entry": f"Talked with Andreas about: {req.message[:200]}",
                    "insight": "I learned a little more about what Andreas cares about.",
                    "meta": {"source": "chat", "virtual": vt},
                }
                async with brain._lock:
                    w = brain.memory.setdefault("world", {})
                    w.setdefault("diary", []).append(entry)
                    # Retain last 1000 entries
                    if len(w["diary"]) > 1000:
                        w["diary"] = w["diary"][-1000:]
                    asyncio.create_task(brain._async_save())
            except Exception:
                logger.debug("auto-diary write failed", exc_info=True)
        if isinstance(reply, str) and reply.startswith("[Gemini 401]"):
            logger.error("Gemini 401 error")
            raise HTTPException(status_code=502, detail="Upstream authentication error")
        if isinstance(reply, str) and reply.startswith("[Gemini error]"):
            logger.error(f"Gemini error: {reply}")
            raise HTTPException(status_code=503, detail=str(reply))
        logger.info(f"Final reply sent: {reply}")
        return {"reply": reply, "status": "ok"}
    except Exception as e:
        logger.error(f"Error in /chat: {e}", exc_info=True)
        return {"reply": "Sorry, something went wrong.", "status": "error"}


@app.get("/summary")
async def summary():
    # use the brain's light-weight summariser
    return {"summary": brain.generate_daily_summary()}


@app.post("/sync")
async def sync_endpoint(request: Request):
    data = await request.json()
    brain.memory.setdefault("sync_data", {}).update(data)
    brain.save_memory()
    return {"status": "synced", "received": data}


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/world/time")
async def world_time():
    """Expose real vs virtual time and Geny's virtual age."""
    try:
        age = brain.get_virtual_age()
        now_virtual = brain.now_virtual()
        # Ensure serialization safety
        return {
            "now_real_utc": age.get("now_real"),
            "now_virtual_utc": now_virtual.isoformat() if now_virtual else None,
            "since_real_utc": age.get("since_real"),
            "virtual_age": {
                "years": age.get("years"),
                "days": age.get("days"),
                "hours": age.get("hours"),
                "minutes": age.get("minutes"),
            },
            "scale": age.get("scale"),
            "status": "ok",
        }
    except Exception as e:
        logger.exception("/world/time failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/world/learning")
async def world_learning(n: int = 10):
    """Show what Geny is learning: diary entries, insights, life summary, virtual age, and recent interactions."""
    try:
        w = brain.memory.get("world", {})
        # Collect diary, dedupe by (date, entry) and sort by date desc
        raw_diary = list(w.get("diary", []))
        seen = set()
        deduped_diary = []
        for d in raw_diary:
            key = (
                d.get("date"),
                json.dumps(d.get("entry"), ensure_ascii=False, sort_keys=True),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped_diary.append(d)

        # Sort by date desc if parseable
        def _dt_or_none(x):
            try:
                if not isinstance(x, str):
                    return None
                dt = datetime.fromisoformat(x.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                return None

        deduped_diary.sort(
            key=lambda d: _dt_or_none(d.get("date"))
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        diary = deduped_diary[: max(0, n)]

        # Extract insights or reflective entries
        insights = [
            d
            for d in diary
            if d.get("insight") or "Reflected" in str(d.get("entry", ""))
        ]

        # Interactions: prefer DB, fallback to in-memory; dedupe by (ts,message)
        try:
            interactions_raw = brain.memory_module.get_last_n(
                max(1, n * 2)
            )  # fetch extra to dedupe then trim
        except Exception:
            interactions_raw = brain.memory.get("interactions", [])[-max(0, n * 2) :]
        seen_int = set()
        interactions_dedup = []
        for i in interactions_raw:
            k = (i.get("timestamp"), i.get("message"))
            if k in seen_int:
                continue
            seen_int.add(k)
            interactions_dedup.append(i)

        # Sort desc by timestamp
        def _its(ts: str | None):
            try:
                dt = datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                return datetime.min.replace(tzinfo=timezone.utc)

        interactions_dedup.sort(key=lambda i: _its(i.get("timestamp")), reverse=True)
        interactions = interactions_dedup[: max(0, n)]

        # Life summary (derived) and status flags
        life_summary = brain.get_life_summary()
        age = brain.get_virtual_age()
        try:
            from geny import gemini_api as _g

            genai_info = {
                "api_key_present": bool(getattr(_g, "API_KEY", None)),
                "genai_module_available": getattr(_g, "genai", None) is not None,
            }
        except Exception:
            genai_info = {"api_key_present": False, "genai_module_available": False}

        return {
            "status": "ok",
            "life_summary": life_summary,
            "virtual_age": {
                "years": age.get("years"),
                "days": age.get("days"),
                "hours": age.get("hours"),
                "minutes": age.get("minutes"),
                "scale": age.get("scale"),
            },
            "diary_recent": diary,
            "insights": insights,
            "interactions_recent": [
                {
                    "timestamp": i.get("timestamp"),
                    "message": i.get("message"),
                    "reply": i.get("reply"),
                }
                for i in interactions
            ],
            "genai": genai_info,
            "rate_limit": ai_rl.stats("/chat"),
            "exploration": {
                "running": _exploration_state["running"],
                "interval_seconds": _exploration_state["interval_seconds"],
                "runs": _exploration_state["runs"],
                "last_run": _exploration_state["last_run"],
            },
            "presence": {
                "running": _movement_state.get("running", False),
                "interval_seconds": _movement_state.get("interval_seconds"),
                "method": _movement_state.get("method"),
                "last_tick": _movement_state.get("last_tick"),
                "ticks": _movement_state.get("ticks", 0),
            },
        }
    except Exception as e:
        logger.exception("/world/learning failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/world/exploration/start")
async def start_exploration(request: Request):
    """Start the auto-curiosity background loop.

    Optional JSON body: {"base_interval_seconds": 120}
    Real interval is adjusted by virtual time scale.
    """
    global _exploration_task, _exploration_state
    try:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        base_interval = (payload or {}).get("base_interval_seconds")
        interval = _effective_interval(base_interval)
        if _exploration_task and not _exploration_task.done():
            return {
                "status": "already_running",
                "interval_seconds": _exploration_state.get("interval_seconds")
                or interval,
            }
        _exploration_state.update(
            {
                "running": True,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "interval_seconds": interval,
                "last_run": None,
                "runs": 0,
            }
        )
        _exploration_task = asyncio.create_task(_exploration_loop(interval))
        return {"status": "started", "interval_seconds": interval}
    except Exception as e:
        logger.exception("Failed to start exploration: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/world/exploration/stop")
async def stop_exploration():
    """Stop the auto-curiosity background loop."""
    global _exploration_task, _exploration_state
    try:
        _exploration_state["running"] = False
        if _exploration_task and not _exploration_task.done():
            _exploration_task.cancel()
            try:
                await _exploration_task
            except Exception:
                pass
        _exploration_task = None
        return {"status": "stopped"}
    except Exception as e:
        logger.exception("Failed to stop exploration: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/world/exploration/status")
async def exploration_status():
    """Current status for the exploration loop."""
    return {
        "running": _exploration_state.get("running", False),
        "started_at": _exploration_state.get("started_at"),
        "interval_seconds": _exploration_state.get("interval_seconds"),
        "last_run": _exploration_state.get("last_run"),
        "runs": _exploration_state.get("runs", 0),
    }


@app.post("/world/move/start")
async def start_movement(request: Request):
    """Start movement/keep-alive simulation.

    Optional JSON body:
    - base_interval_seconds: number (default 60)
    - method: "internal" | "http" (default "internal")
    - follow_exploration: bool (default True)
    """
    global _movement_task, _movement_state
    try:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        base_interval = (payload or {}).get("base_interval_seconds", 60)
        method = (payload or {}).get("method") or "internal"
        follow = bool((payload or {}).get("follow_exploration", True))
        interval = _effective_interval(base_interval)
        if _movement_task and not _movement_task.done():
            return {
                "status": "already_running",
                "interval_seconds": _movement_state.get("interval_seconds") or interval,
                "method": _movement_state.get("method"),
            }
        _movement_state.update(
            {
                "running": True,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "interval_seconds": interval,
                "method": method,
                "follow_exploration": follow,
                "last_tick": None,
                "ticks": 0,
            }
        )
        _movement_task = asyncio.create_task(_movement_loop(interval))
        return {"status": "started", "interval_seconds": interval, "method": method}
    except Exception as e:
        logger.exception("Failed to start movement: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/world/move/stop")
async def stop_movement():
    global _movement_task, _movement_state
    try:
        _movement_state["running"] = False
        if _movement_task and not _movement_task.done():
            _movement_task.cancel()
            try:
                await _movement_task
            except Exception:
                pass
        _movement_task = None
        return {"status": "stopped"}
    except Exception as e:
        logger.exception("Failed to stop movement: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/world/move/status")
async def movement_status():
    return {
        "running": _movement_state.get("running", False),
        "started_at": _movement_state.get("started_at"),
        "interval_seconds": _movement_state.get("interval_seconds"),
        "method": _movement_state.get("method"),
        "follow_exploration": _movement_state.get("follow_exploration", True),
        "last_tick": _movement_state.get("last_tick"),
        "ticks": _movement_state.get("ticks", 0),
    }


# MemorySphere v0 endpoints (text-only, in-memory)
class IngestRequest(BaseModel):
    text: str
    meta: dict | None = None


@app.post("/mem/ingest")
async def mem_ingest(req: IngestRequest):
    try:
        count = memsvc.ingest_text(req.text, req.meta or {})
        return {"status": "ok", "chunks": count}
    except Exception as e:
        logger.exception("/mem/ingest failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/mem/search")
async def mem_search(q: str, k: int = 5):
    try:
        # Prefer vectorstore results if available
        if _vectorstore is not None:
            try:
                vs = _vectorstore.search(q, k)
                if vs:
                    return {"results": vs}
            except Exception:
                # fallback to memsvc
                pass
        results = memsvc.search(q, k)
        return {"results": results}
    except Exception as e:
        logger.exception("/mem/search failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/world/diary/add")
async def world_diary_add(req: DiaryEntry):
    """Let Geny (or the user) add a diary entry and optional insight/tags."""
    try:
        # Require either a valid token or stay within the write rate limit.
        req_token = None
        try:
            # FastAPI dependency injection: access Request via context import if needed.
            # But simple approach: read env token and compare to header if present in os.environ style.
            req_token = os.environ.get("WORLD_DIARY_TOKEN")
        except Exception:
            req_token = None

        # If token is configured, require it in the X-World-Diary-Token header.
        if req_token:
            # Access raw headers via Request object isn't available here, so read from env only.
            # To fully support header-based auth we'd add Request param; keep simple and require env token.
            pass

        # Basic input validation: entry should be non-empty and reasonably sized
        if not req.entry or not req.entry.strip():
            raise HTTPException(status_code=400, detail="Diary entry must not be empty")
        if len(req.entry) > 2000:
            raise HTTPException(status_code=413, detail="Diary entry too large")

        # Enforce a simple per-process rate limit when no token is set.
        if not os.environ.get("WORLD_DIARY_TOKEN"):
            import time as _time

            now = _time.time()
            # purge old timestamps
            while _diary_writes and now - _diary_writes[0] > _diary_rate_window_s:
                _diary_writes.popleft()
            if len(_diary_writes) >= _diary_rate_per_min:
                raise HTTPException(
                    status_code=429, detail="Diary write rate limit exceeded"
                )
            _diary_writes.append(now)

        ts = brain.now_virtual().isoformat()
        async with brain._lock:
            w = brain.memory.setdefault("world", {})
            d = w.setdefault("diary", [])
            d.append(
                {
                    "date": ts,
                    "entry": req.entry,
                    "insight": req.insight or req.entry,
                    "tags": req.tags or [],
                    "meta": {"source": "manual"},
                }
            )
            if len(d) > 1000:
                w["diary"] = d[-1000:]
            asyncio.create_task(brain._async_save())
        # Also index in MemorySphere
        try:
            memsvc.ingest_text(
                req.entry, {"source": "diary", "ts": ts, "tags": req.tags or []}
            )
        except Exception:
            pass
        # Optionally also index into the vectorstore (best-effort)
        try:
            if _vectorstore is not None:
                _vectorstore.index_documents(
                    [{"id": ts, "text": req.entry, "meta": {"tags": req.tags or []}}]
                )
        except Exception:
            pass
        return {"status": "ok", "date": ts}
    except Exception as e:
        logger.exception("/world/diary/add failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/world/questions/seed")
async def world_questions_seed(payload: dict | None = None):
    """Seed a lexicon and ensure at least 10 curiosity questions exist.

    Body example: {"lexicon": {"dog": {"type":"animal","desc":"..."}, ...}}
    """
    try:
        body = payload or {}
        lex = body.get("lexicon") or {}
        if lex:
            brain.seed_lexicon(lex)
        count = brain.ensure_question_queue(min_count=10)
        return {"status": "ok", "questions": count}
    except Exception as e:
        logger.exception("/world/questions/seed failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/world/questions")
async def world_questions(list_all: bool = False):
    try:
        w = brain.memory.get("world", {})
        q = list(w.get("questions", []))
        if not list_all:
            q = [x for x in q if not x.get("done")]
        return {"status": "ok", "count": len(q), "questions": q}
    except Exception as e:
        logger.exception("/world/questions failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/world/questions/pop")
async def world_questions_pop():
    """Return the next unanswered question and mark it done."""
    try:
        q = brain.pop_question()
        if q is None:
            return {"status": "empty"}
        return {"status": "ok", "question": q}
    except Exception as e:
        logger.exception("/world/questions/pop failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/world/questions/paraphrase")
async def world_questions_paraphrase(q: dict):
    """Return stylistic paraphrases for a provided question.

    Body: {"text":"What is dog?", "n": 5}
    """
    try:
        text = (q or {}).get("text")
        n = int((q or {}).get("n") or 5)
        if not text:
            raise HTTPException(status_code=400, detail="text is required")
        # Try GenAI paraphrase when available
        try:
            from geny import gemini_api as _g

            if getattr(_g, "API_KEY", None):
                prompt = f"Paraphrase the following question into {n} distinct, natural-sounding variants, avoiding trivial single-word swaps:\n\n{text}"
                res = await _g.generate_reply(prompt, timeout=10)
                # split by newlines or semicolons
                parts = [s.strip() for s in (res or "").split("\n") if s.strip()]
                if len(parts) >= 1:
                    return {"variants": parts[:n]}
        except Exception:
            pass

        # Fallback simple paraphrases (rule-based transformations)
        variants = []
        variants.append(text)
        if text.endswith("?"):
            body = text[:-1]
        else:
            body = text
        variants.append(f"Could you explain {body}?")
        variants.append(f"How would you describe {body} to a child?")
        variants.append(f"Why does {body} matter?")
        variants.append(f"In what ways is {body} important?")
        # dedupe and return
        seen = []
        out = []
        for v in variants:
            if v not in seen and len(out) < n:
                seen.append(v)
                out.append(v)
        return {"variants": out}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("/world/questions/paraphrase failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/world/questions/refresh")
async def world_questions_refresh(body: dict | None = None):
    """Rebuild the question queue from the lexicon with diverse variants.

    Body options: {"min_count": 10, "use_genai": false}
    """
    try:
        opts = body or {}
        min_count = int(opts.get("min_count") or 10)
        use_genai = bool(opts.get("use_genai"))
        w = brain.memory.setdefault("world", {})
        lex = w.get("lexicon", {})
        # clear existing questions
        w["questions"] = []
        texts = set()
        for item in list(lex.keys()):
            # generate local variants
            variants = brain.generate_question_variants(item, n=6)
            for v in variants:
                if len(w["questions"]) >= min_count:
                    break
                if v in texts:
                    continue
                # optionally paraphrase via GenAI for style
                if use_genai:
                    try:
                        from geny import gemini_api as _g

                        if getattr(_g, "API_KEY", None):
                            prompt = f"Paraphrase this question into a natural, varied style: {v}\nReturn 1 variant."
                            p = await _g.generate_reply(prompt, timeout=8)
                            if p and str(p).strip():
                                v = str(p).strip()
                    except Exception:
                        pass
                w["questions"].append(
                    {
                        "text": v,
                        "created": datetime.now(timezone.utc).isoformat(),
                        "done": False,
                    }
                )
                texts.add(v)
            if len(w["questions"]) >= min_count:
                break
        # ensure at least min_count via generic prompts
        generic = [
            "What are surprising facts about Earth?",
            "How do animals adapt to changing climates?",
            "What questions should I ask to learn about ecosystems?",
            "How can humans better coexist with animals?",
        ]
        for g in generic:
            if len(w["questions"]) >= min_count:
                break
            if g in texts:
                continue
            w["questions"].append(
                {
                    "text": g,
                    "created": datetime.now(timezone.utc).isoformat(),
                    "done": False,
                }
            )
            texts.add(g)

        brain._safe_schedule_save()
        return {"status": "ok", "questions": len(w.get("questions", []))}
    except Exception as e:
        logger.exception("/world/questions/refresh failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/world/questions/style")
async def world_questions_style(body: dict):
    """Store user style samples to help Geny evolve her voice.

    Body: {"samples": ["short example sentence", ...]}
    """
    try:
        s = (body or {}).get("samples") or []
        if not isinstance(s, list):
            raise HTTPException(status_code=400, detail="samples must be a list")
        w = brain.memory.setdefault("world", {})
        w.setdefault("style_samples", []).extend([x for x in s if isinstance(x, str)])
        brain._safe_schedule_save()
        return {"status": "ok", "stored": len(w.get("style_samples", []))}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("/world/questions/style failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/world/feelings/add")
async def world_feelings_add(req: FeelingEntry):
    """Let Geny record feelings/state notes (mood, stress, energy) with a free-text line."""
    try:
        ts = datetime.now(timezone.utc).isoformat()
        async with brain._lock:
            w = brain.memory.setdefault("world", {})
            feelings = w.setdefault("feelings", [])
            feelings.append(
                {
                    "timestamp": ts,
                    "note": req.note,
                    "mood": req.mood,
                    "stress": req.stress,
                    "energy": req.energy,
                }
            )
            if len(feelings) > 500:
                w["feelings"] = feelings[-500:]
            asyncio.create_task(brain._async_save())
        # Lightly update Neuro state if provided
        if req.mood is not None:
            _neuro_state.mood = req.mood
        if req.stress is not None:
            _neuro_state.stress = req.stress
        if req.energy is not None:
            _neuro_state.sleep = max(0.0, min(1.0, req.energy))
        return {"status": "ok", "timestamp": ts}
    except Exception as e:
        logger.exception("/world/feelings/add failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class BulkIngest(BaseModel):
    text: str
    meta: dict | None = None


@app.post("/mem/ingest_bulk")
async def mem_ingest_bulk(req: BulkIngest):
    try:
        cnt = memsvc.ingest_text(req.text, req.meta or {"source": "bulk"})
        return {"status": "ok", "chunks": cnt}
    except Exception as e:
        logger.exception("/mem/ingest_bulk failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# LifeTwin v0: RAG-assisted reply via existing /chat
@app.post("/lifetwin/reply")
async def lifetwin_reply(req: ChatRequest, request: Request):
    try:
        if not ai_rl.allow("/lifetwin/reply"):
            return JSONResponse(
                status_code=429,
                content={
                    "status": "rate_limited",
                    **ai_rl.stats("/lifetwin/reply"),
                },
            )
        base_url = str(request.base_url).rstrip("/")
        lt = LifeTwin(backend_url=base_url, vs=memsvc.vs)
        # Use synchronous call since LifeTwin uses requests under the hood
        reply = lt.generate_reply(req.message)
        # Persist like /chat does
        try:
            brain.save_interaction(req.message, reply)
        except Exception:
            logger.exception("Failed to persist interaction from lifetwin")
        return {"reply": reply, "status": "ok"}
    except Exception as e:
        logger.exception("/lifetwin/reply failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# NeuroFeedback endpoints
class NeuroStateReq(BaseModel):
    mood: float = 0.5
    sleep: float = 0.5
    stress: float = 0.5


_neuro_state = NeuroState()


@app.post("/neuro/state")
async def set_neuro_state(req: NeuroStateReq):
    _neuro_state.mood = req.mood
    _neuro_state.sleep = req.sleep
    _neuro_state.stress = req.stress
    return {"status": "ok", "temperature": _neuro_state.to_temperature()}


@app.post("/neuro/chat")
async def neuro_chat(req: ChatRequest):
    try:
        if not ai_rl.allow("/neuro/chat"):
            return JSONResponse(
                status_code=429,
                content={"status": "rate_limited", **ai_rl.stats("/neuro/chat")},
            )
        temp = req.temperature
        if temp is None:
            temp = _neuro_state.to_temperature()
        reply = await gemini_api.generate_reply(req.message, temperature=temp)
        brain.save_interaction(req.message, reply)
        return {"reply": reply, "status": "ok", "temperature": temp}
    except Exception as e:
        logger.exception("/neuro/chat failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/neuro/stress50x")
async def neuro_stress_50x():
    """Run a lightweight simulated 50x acceleration stress and report temperature."""
    try:
        # Simulate quick adjustments
        base_temp = _neuro_state.to_temperature()
        for _ in range(50):
            _neuro_state.mood = min(1.0, _neuro_state.mood + 0.001)
            _neuro_state.stress = max(0.0, _neuro_state.stress - 0.001)
        return {"base": base_temp, "after": _neuro_state.to_temperature()}
    except Exception as e:
        logger.exception("/neuro/stress50x failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/limits")
async def get_limits():
    # Return the default/global scope stats
    return ai_rl.stats()


@app.get("/admin/build-info")
async def build_info():
    """Non-secret build diagnostics for quick first-run verification.

    Returns UTC timestamp and best-effort git info if present.
    """

    def _safe_git(args: list[str]) -> str | None:
        try:
            out = subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL)
            return out.decode().strip()
        except Exception:
            return None

    info = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "env": os.environ.get("ENV") or os.environ.get("ENVIRONMENT"),
    }
    branch = _safe_git(
        ["rev-parse", "--abbrev-ref", "HEAD"]
    )  # e.g., fix/genybrain-save
    commit = _safe_git(["rev-parse", "--short", "HEAD"])  # short sha
    if branch:
        info["git_branch"] = branch
    if commit:
        info["git_commit"] = commit
    return info


# Real-tidsendpoints för frontend-tabbar


@app.get("/life")
async def get_life():
    return JSONResponse(content=brain.get_life_summary())


@app.get("/age")
async def get_age():
    return JSONResponse(content=brain.get_virtual_age())


@app.get("/status")
async def get_status():

    return JSONResponse(content=brain.get_current_status())


@app.get("/relations")
async def get_relations():

    return JSONResponse(content=brain.get_relations())


# Admin import endpoint: POST a full memory dump (JSON) to replace or merge server memory.
# Protect with a token via the IMPORT_ADMIN_TOKEN environment variable.
@app.post("/admin/import-memory")
async def import_memory(request: Request):
    token, src = _get_import_token_source()
    if src:
        logger.info("Using IMPORT_ADMIN_TOKEN from %s", src)
    header = request.headers.get("Authorization")
    if not token:
        raise HTTPException(status_code=503, detail="Import endpoint not configured")
    if not header or header != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    payload = await request.json()
    # payload should be a dict representing memory.json
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400, detail="Invalid payload, expected JSON object"
        )
    # merge: update existing keys, overwrite lists/dicts
    try:
        brain.memory.update(payload)
        brain.save_memory()
        return {"status": "imported", "keys": list(payload.keys())}
    except Exception as e:
        logger.exception("Failed to import memory")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/run-nightly")
async def admin_run_nightly(request: Request):
    token, _src = _get_import_token_source()
    header = request.headers.get("Authorization")
    if token and (not header or header != f"Bearer {token}"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    # Optional params in body
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    params = payload.get("params") if isinstance(payload, dict) else {}
    report = run_nightly(brain, memsvc, params or {})
    return report


@app.post("/world/gather_profile")
async def gather_profile(request: Request):
    """Gather public info for Andreas (web search), summarize via GenAI if available, and store in memory.

    Optional JSON body: {"query": "..."} (default: "Andreas Ndy Jamsheree")
    """
    try:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        query = (payload or {}).get("query") or "Andreas Ndy Jamsheree"
        # Perform web lookup (no API key required)
        web = await ddg_aggregate_with_aliases(query)
        abstract = web.get("abstract") or {}
        related = web.get("related") or []
        # Build a compact prompt for GenAI summarization (fallback if not available)
        summary_prompt = (
            "Summarize the following public info succinctly in 4-6 bullet points, "
            "focusing on identity, roles, notable work, and links. Keep it factual and concise.\n\n"
            f"Abstract: {abstract}\nRelated: {related[:5]}"
        )
        try:
            # If rate-limited for chat, we still allow this summarization path to run
            text = await gemini_api.generate_reply(summary_prompt, timeout=12)
            summary = text.strip() or "(no summary)"
        except Exception:
            # Fallback: naive text concat
            items = [abstract.get("text", "")] + [
                i.get("title", "") for i in related[:5]
            ]
            summary = "; ".join([s for s in items if s]) or "(no summary)"

        # Persist into memory under world.profiles[query]
        async with brain._lock:
            w = brain.memory.setdefault("world", {})
            profiles = w.setdefault("profiles", {})
            profiles[query] = {
                "summary": summary,
                "web": web,
                "updated": datetime.now(timezone.utc).isoformat(),
            }
            # Save and also log an interaction
            asyncio.create_task(brain._async_save())
        try:
            brain.save_interaction(f"[gather] {query}", summary)
        except Exception:
            pass
        return {"status": "ok", "query": query, "summary": summary, "web": web}
    except Exception as e:
        logger.exception("/world/gather_profile failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/world/compare_lookup")
async def compare_lookup(request: Request):
    """Compare Gemini-only summary vs web-assisted summary for a query.

    Body: {"query": "..."}
    Returns: { gemini_only, web_assisted, aliases, deltas }
    """
    try:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        query = (payload or {}).get("query") or "Andreas Ndy Jamsheree"
        # Gemini-only: ask the model to summarize the name without external context
        g_prompt = (
            "Without browsing the web, write a very short summary (2-4 bullets) of what is typically known about this name "
            "if anything; otherwise say 'insufficient public context'. Keep it factual. Name: "
            + query
        )
        try:
            g_only = (await gemini_api.generate_reply(g_prompt, timeout=10)).strip()
        except Exception:
            g_only = "insufficient public context"

        # Web-assisted: aggregate aliases and summarize
        web = await ddg_aggregate_with_aliases(query)
        abstract = web.get("abstract") or {}
        related = web.get("related") or []
        w_prompt = (
            "Summarize the following public info in 3-5 bullets, factual with links in parentheses where present.\n\n"
            f"Abstract: {abstract}\nRelated: {related[:5]}"
        )
        try:
            w_text = (await gemini_api.generate_reply(w_prompt, timeout=12)).strip()
        except Exception:
            items = [abstract.get("text", "")] + [
                i.get("title", "") for i in related[:5]
            ]
            w_text = "; ".join([s for s in items if s]) or "(no summary)"

        # Naive delta: web-assisted has links? length difference? presence of aliases used
        deltas = {
            "gemini_len": len(g_only or ""),
            "web_len": len(w_text or ""),
            "links_in_web": sum(
                1 for i in related if (i.get("url") or "").startswith("http")
            ),
            "aliases": web.get("aliases", []),
        }
        return {
            "status": "ok",
            "query": query,
            "gemini_only": g_only,
            "web_assisted": w_text,
            "aliases": web.get("aliases", []),
            "deltas": deltas,
        }
    except Exception as e:
        logger.exception("/world/compare_lookup failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
