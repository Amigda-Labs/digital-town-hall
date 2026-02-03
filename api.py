"""
FastAPI server for Digital Town Hall backend.
Phase 1: Minimal echo server with SSE streaming.
"""

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


app = FastAPI(title="Digital Town Hall API")

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


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str
    session_id: str | None = None


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Digital Town Hall API",
        "version": "0.1.0",
        "phase": "1 - Echo Server"
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Chat endpoint with Server-Sent Events (SSE) streaming.
    Phase 1: Simply echoes back the message word-by-word.
    """

    async def event_generator():
        """Generator that yields SSE-formatted events."""

        # Simulate streaming by sending message word-by-word
        words = request.message.split()

        for i, word in enumerate(words):
            # SSE format: "data: <content>\n\n"
            yield f"data: {word}\n\n"
            await asyncio.sleep(0.1)  # Simulate processing delay

        # Send completion signal
        yield f"data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx
        }
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
