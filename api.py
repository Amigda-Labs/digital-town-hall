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
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def get_device_id_or_ip(request: Request) -> str:
    """Use X-Device-ID header as rate limit key, fall back to IP."""
    return request.headers.get("X-Device-ID") or get_remote_address(request)


limiter = Limiter(key_func=get_device_id_or_ip)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized (driver=%s)", "postgresql" if "postgresql" in DATABASE_URL else "sqlite")
    yield
    logger.info("Shutting down...")


app = FastAPI(title="Digital Town Hall API", lifespan=lifespan)
app.state.limiter = limiter
def _rate_limit_handler(req: Request, exc: RateLimitExceeded) -> Response:
    device_id = req.headers.get("X-Device-ID", "anonymous")
    logger.warning("rate_limit_exceeded path=%s device=%s", req.url.path, device_id)
    return Response(
        content='{"detail":"Rate limit exceeded. Please slow down."}',
        status_code=429,
        media_type="application/json",
    )

app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log every incoming request and its response time."""
    start = time.monotonic()
    device_id = request.headers.get("X-Device-ID", "anonymous")
    logger.info("request_start method=%s path=%s device=%s", request.method, request.url.path, device_id)
    response = await call_next(request)
    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info("request_end method=%s path=%s status=%s duration_ms=%.1f", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


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
    logger.info("chatkit_request device=%s", device_id or "anonymous")
    try:
        result = await chatkit_server.process(await request.body(), context={"device_id": device_id})
    except Exception:
        logger.exception("chatkit_error device=%s", device_id or "anonymous")
        raise
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
