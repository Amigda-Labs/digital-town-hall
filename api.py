"""
FastAPI server for Digital Town Hall backend.
 Phase 2: Connected to actual agent streaming logic with session management.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Import agent components
from agents import Runner, trace
from agents.extensions.memory import SQLAlchemySession
from core.context import TownHallContext
from core.database import init_db, DATABASE_URL
from town_hall_agents import dialogue_agent
from openai.types.responses import ResponseTextDeltaEvent


# Session storage (in-memory for Phase 2)
# Structure: {session_id: {context, sql_session, current_agent}}
sessions = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: Initialize database
    print("🚀 Initializing database...")
    await init_db()
    print("✅ Database initialized")
    print(f"📁 Database URL: {DATABASE_URL}")
    yield
    # Shutdown: cleanup if needed
    print("👋 Shutting down...")


app = FastAPI(title="Digital Town Hall API", lifespan=lifespan)

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
        "version": "0.2.0",
        "phase": "2 - Agent Streaming Connected",
        "active_sessions": len(sessions)
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Chat endpoint with Server-Sent Events (SSE) streaming.
    Phase 2: Streams responses from actual Town Hall agents.

    Request body:
    - message: User's message
    - session_id: Optional session identifier. If not provided, creates a new session.

    Returns:
    - Server-Sent Events stream with agent responses
    """

    # Get or create session
    session_id = request.session_id or f"user-{uuid.uuid4()}"

    if session_id not in sessions:
        # Create new session (same as main.py does)
        print(f"📝 Creating new session: {session_id}")
        sessions[session_id] = {
            "context": TownHallContext(session_id=session_id),
            "sql_session": SQLAlchemySession.from_url(
                session_id,
                url=DATABASE_URL,
                create_tables=True,
            ),
            "current_agent": dialogue_agent,
        }
    else:
        print(f"♻️  Using existing session: {session_id}")

    session_data = sessions[session_id]

    async def event_generator():
        """Generator that streams agent responses as SSE events."""
        try:
            # Run agent with streaming (same as main.py lines 56-70)
            with trace("Town Hall API Conversation"):
                result = Runner.run_streamed(
                    session_data["current_agent"],
                    request.message,
                    session=session_data["sql_session"],
                    context=session_data["context"],
                )

                # Stream events as they arrive
                async for event in result.stream_events():
                    if event.type == "raw_response_event" and isinstance(
                        event.data, ResponseTextDeltaEvent
                    ):
                        # Send text delta in SSE format
                        delta = event.data.delta
                        if delta:
                            yield f"data: {delta}\n\n"

                # Update current agent for next turn (same as main.py line 70)
                session_data["current_agent"] = result.last_agent

                # Send completion signal
                yield f"data: [DONE]\n\n"

        except Exception as e:
            print(f"❌ Error in chat: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: [ERROR: {str(e)}]\n\n"

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


@app.get("/sessions")
async def list_sessions():
    """List all active sessions (for debugging)."""
    return {
        "total": len(sessions),
        "session_ids": list(sessions.keys())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
