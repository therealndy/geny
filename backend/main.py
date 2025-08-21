
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from geny.geny_brain import GenyBrain
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

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

