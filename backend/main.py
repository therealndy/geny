
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

@app.post("/chat")
async def chat(req: ChatRequest):
    reply = await brain.generate_reply(req.message)
    if isinstance(reply, str) and reply.startswith("[Gemini 401]"):
        raise HTTPException(status_code=502, detail="Upstream authentication error")
    if isinstance(reply, str) and reply.startswith("[Gemini error]"):
        raise HTTPException(status_code=503, detail=str(reply))
    return {"reply": reply, "status": "ok"}

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

