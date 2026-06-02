from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.games import router as games_router
from backend.api.websocket import router as ws_router

app = FastAPI(
    title="BeerGame: The Next Level",
    version="0.1.0",
    description="Multi-variant Beer Game serious game platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten per-variant in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(games_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
