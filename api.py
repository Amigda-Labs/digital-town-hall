"""
FastAPI server for Digital Town Hall backend.
"""

from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from core.database import init_db, DATABASE_URL
from chatkit.server import StreamingResult
from core.sqlalchemy_store import SQLAlchemyStore
from core.chatkit_server import TownHallChatKitServer

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def get_device_id_or_ip(request: Request) -> str:
    """Use X-Device-ID header as rate limit key, fall back to IP."""
    return request.headers.get("X-Device-ID") or get_remote_address(request)


limiter = Limiter(key_func=get_device_id_or_ip)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("🚀 Initializing database...")
    await init_db()
    print("✅ Database initialized")
    print(f"📁 Database URL: {DATABASE_URL}")
    yield
    print("👋 Shutting down...")


app = FastAPI(title="Digital Town Hall API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda req, exc: Response(
    content='{"detail":"Rate limit exceeded. Please slow down."}',
    status_code=429,
    media_type="application/json",
))
app.add_middleware(SlowAPIMiddleware)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js default
        "http://localhost:3001",  # Alternative port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Digital Town Hall API",
        "version": "0.4.0",
        "phase": "4 - Clean api.py for ChatKit Integration",
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

# ==== Chatkit ====
store = SQLAlchemyStore()
chatkit_server = TownHallChatKitServer(store=store)

@app.post("/chatkit")
@limiter.limit("15/minute")
async def chatkit_endpoint(request: Request):
    """Single ChatKit endpoint — handles threads, messages, and streaming."""
    device_id = request.headers.get("X-Device-ID")
    result = await chatkit_server.process(await request.body(), context={"device_id": device_id})
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    return Response(content=result.json, media_type="application/json")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
