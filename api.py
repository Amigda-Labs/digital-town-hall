"""
FastAPI server for Digital Town Hall backend.
Phase 3: Enhanced session management with metadata, tracing, and anonymous user support.
"""

import asyncio
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Import agent components
from agents import Runner, trace
from agents.extensions.memory import SQLAlchemySession
from core.context import TownHallContext
from core.database import init_db, DATABASE_URL
from town_hall_agents import dialogue_agent
from openai.types.responses import ResponseTextDeltaEvent


class SessionData(BaseModel):
    """Enhanced session data with metadata."""
    session_id: str
    user_id: str  # User identifier for grouping sessions (can be anonymous)
    group_id: str  # Group identifier for tracing
    created_at: datetime
    last_active: datetime
    message_count: int = 0

    class Config:
        arbitrary_types_allowed = True


# Session storage (in-memory for Phase 3)
# Structure: {session_id: {metadata: SessionData, context, sql_session, current_agent}}
sessions: Dict[str, Dict[str, Any]] = {}


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


class CreateSessionRequest(BaseModel):
    """Request model for creating a new session."""
    user_id: str | None = Field(
        None,
        description="User identifier. If not provided, generates anonymous user ID (for users not logged in)"
    )


class CreateSessionResponse(BaseModel):
    """Response model for session creation."""
    session_id: str
    user_id: str
    group_id: str
    created_at: datetime


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str
    session_id: str


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Digital Town Hall API",
        "version": "0.3.0",
        "phase": "3 - Enhanced Session Management + Anonymous Users",
        "active_sessions": len(sessions)
    }


@app.post("/sessions/create", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """
    Create a new session for a user.

    Supports anonymous users (not logged in):
    - If user_id is provided: Use it directly
    - If user_id is None: Generate anonymous-{uuid} for this browser/device

    Frontend should store the user_id in localStorage and reuse it.

    Each session has:
    - session_id: Unique identifier for this conversation
    - user_id: User identifier (can have multiple sessions)
    - group_id: For tracing/analytics (groups all sessions by this user)
    """
    # Support anonymous users - generate ID if not provided
    user_id = request.user_id or f"anonymous-{uuid.uuid4()}"
    session_id = f"session-{uuid.uuid4()}"
    group_id = f"user-group-{user_id}"
    now = datetime.utcnow()

    print(f"📝 Creating new session: {session_id} for user: {user_id}")

    # Create session metadata
    metadata = SessionData(
        session_id=session_id,
        user_id=user_id,
        group_id=group_id,
        created_at=now,
        last_active=now,
        message_count=0
    )

    # Create agent components
    sessions[session_id] = {
        "metadata": metadata,
        "context": TownHallContext(session_id=session_id),
        "sql_session": SQLAlchemySession.from_url(
            session_id,
            url=DATABASE_URL,
            create_tables=True,
        ),
        "current_agent": dialogue_agent,
    }

    return CreateSessionResponse(
        session_id=session_id,
        user_id=user_id,
        group_id=group_id,
        created_at=now
    )


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session information and metadata."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    session_data = sessions[session_id]
    metadata = session_data["metadata"]

    return {
        "session_id": metadata.session_id,
        "user_id": metadata.user_id,
        "group_id": metadata.group_id,
        "created_at": metadata.created_at,
        "last_active": metadata.last_active,
        "message_count": metadata.message_count,
        "current_agent": session_data["current_agent"].name
    }


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and free resources."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    print(f"🗑️  Deleting session: {session_id}")
    del sessions[session_id]

    return {"status": "deleted", "session_id": session_id}


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Chat endpoint with Server-Sent Events (SSE) streaming.
    Phase 3: Enhanced with session management and tracing metadata.

    Request body:
    - message: User's message
    - session_id: Session identifier (required, use POST /sessions/create first)

    Returns:
    - Server-Sent Events stream with agent responses
    """

    # Validate session exists
    if request.session_id not in sessions:
        raise HTTPException(
            status_code=404,
            detail=f"Session {request.session_id} not found. Create a session first using POST /sessions/create"
        )

    session_data = sessions[request.session_id]
    metadata = session_data["metadata"]

    # Update session activity
    metadata.last_active = datetime.utcnow()
    metadata.message_count += 1

    print(f"💬 Message #{metadata.message_count} in session {request.session_id} (user: {metadata.user_id})")

    async def event_generator():
        """Generator that streams agent responses as SSE events."""
        try:
            # Run agent with streaming + trace metadata (group_id for grouping by user)
            with trace(
                "Town Hall API Conversation",
                metadata={
                    "session_id": metadata.session_id,
                    "user_id": metadata.user_id,
                    "group_id": metadata.group_id,  # Groups all sessions for this user
                    "message_count": metadata.message_count,
                }
            ):
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

                # Update current agent for next turn
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
async def list_sessions(user_id: str | None = None):
    """
    List all active sessions.
    Optionally filter by user_id to see all sessions for a specific user.
    """
    all_sessions = []

    for session_id, session_data in sessions.items():
        metadata = session_data["metadata"]

        # Filter by user_id if provided
        if user_id and metadata.user_id != user_id:
            continue

        all_sessions.append({
            "session_id": metadata.session_id,
            "user_id": metadata.user_id,
            "group_id": metadata.group_id,
            "created_at": metadata.created_at,
            "last_active": metadata.last_active,
            "message_count": metadata.message_count,
        })

    return {
        "total": len(all_sessions),
        "sessions": all_sessions
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
