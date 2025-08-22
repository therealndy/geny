
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from geny.geny_brain import GenyBrain
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

# Tillåt CORS för alla origins (för utveckling)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

brain = GenyBrain()
geny = brain

class ChatRequest(BaseModel):
    message: str


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("geny_backend")

def _get_import_token_source():
    """Return (token, source) where source is 'env', 'file', or None.
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


# Log whether the IMPORT_ADMIN_TOKEN is present at process startup (do not log the value)
_token, _source = _get_import_token_source()
logger.info("IMPORT_ADMIN_TOKEN source at startup: %s", _source)

@app.post("/chat")
async def chat(req: ChatRequest):
    logger.info(f"/chat endpoint received: {req.message}")
    try:
        reply = await brain.generate_reply(req.message)
        # Coerce None to safe fallback
        if reply is None:
            reply = "BRAIN - Sorry, I couldn't generate a reply right now."
        logger.info(f"Geny reply: {reply}")
        # Always persist the interaction via MemoryModule for consistency
        try:
            brain.save_interaction(req.message, reply)
        except Exception:
            logger.exception("Failed to persist interaction")
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
        raise HTTPException(status_code=400, detail="Invalid payload, expected JSON object")
    # merge: update existing keys, overwrite lists/dicts
    try:
        brain.memory.update(payload)
        brain.save_memory()
        return {"status": "imported", "keys": list(payload.keys())}
    except Exception as e:
        logger.exception("Failed to import memory")
        raise HTTPException(status_code=500, detail=str(e))

