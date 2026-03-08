"""
SQLAlchemy database models and utilities for persisting Incidents, Feedback,
and ChatKit threads/items.

This module provides:
- SQLAlchemy ORM models for database storage
- Async database session management
- Helper functions to save Pydantic models to the database
"""

import os
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, Boolean, Date, DateTime, Text, ForeignKey, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Database URL - same as used in main.py for consistency
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///town_hall.db")

# Detect if using PostgreSQL (Supabase) vs SQLite
IS_POSTGRES = DATABASE_URL.startswith("postgresql")

# PgBouncer (Supabase) requires statement_cache_size=0
# SQLite does not support connect_args with this setting
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"statement_cache_size": 0} if IS_POSTGRES else {},
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class IncidentModel(Base):
    """SQLAlchemy model for storing incidents in the database."""
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(255), index=True)
    incident_type: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    date_of_occurrence: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    location: Mapped[str] = mapped_column(String(255))
    person_involved: Mapped[str] = mapped_column(String(255))
    reporter_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    severity_level: Mapped[int] = mapped_column(Integer)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Incident(id={self.id}, type={self.incident_type}, severity={self.severity_level})>"


class FeedbackModel(Base):
    """SQLAlchemy model for storing feedback in the database."""
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(255), index=True)
    topic: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    sentiment: Mapped[str] = mapped_column(String(50))  # "positive", "neutral", "negative"
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Feedback(id={self.id}, topic={self.topic}, sentiment={self.sentiment})>"


class ChatKitThreadModel(Base):
    """Persists ChatKit thread metadata (title, status, etc.)."""
    __tablename__ = "chatkit_threads"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status_json: Mapped[str] = mapped_column(Text, nullable=False, default='{"type":"active"}')
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)


class ChatKitThreadItemModel(Base):
    """Persists a single ChatKit thread item as a JSON blob."""
    __tablename__ = "chatkit_thread_items"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    thread_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("chatkit_threads.id", ondelete="CASCADE"), index=True,
    )
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    item_json: Mapped[str] = mapped_column(Text, nullable=False)


async def init_db():
    """Create all database tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migrate existing databases: add device_id column if missing
        if IS_POSTGRES:
            await conn.execute(text(
                "ALTER TABLE chatkit_threads ADD COLUMN IF NOT EXISTS device_id VARCHAR(255)"
            ))
        else:
            existing = await conn.execute(text("PRAGMA table_info(chatkit_threads)"))
            columns = [row[1] for row in existing.fetchall()]
            if "device_id" not in columns:
                await conn.execute(text(
                    "ALTER TABLE chatkit_threads ADD COLUMN device_id VARCHAR(255)"
                ))


async def save_incident(incident, session_id: str) -> IncidentModel:
    """
    Save a Pydantic Incident model to the database.
    
    Args:
        incident: Pydantic Incident model from core.models
        session_id: The session identifier to associate with this incident
        
    Returns:
        The saved IncidentModel with generated ID
    """
    async with AsyncSessionLocal() as session:
        db_incident = IncidentModel(
            session_id=session_id,
            incident_type=incident.incident_type,
            description=incident.description,
            date_of_occurrence=incident.date_of_occurrence,
            location=incident.location,
            person_involved=incident.person_involved,
            reporter_name=incident.reporter_name,
            severity_level=incident.severity_level,  # Note: matches typo in Pydantic model
        )
        session.add(db_incident)
        await session.commit()
        await session.refresh(db_incident)
        return db_incident


async def save_feedback(feedback, session_id: str) -> FeedbackModel:
    """
    Save a Pydantic Feedback model to the database.
    
    Args:
        feedback: Pydantic Feedback model from core.models
        session_id: The session identifier to associate with this feedback
        
    Returns:
        The saved FeedbackModel with generated ID
    """
    async with AsyncSessionLocal() as session:
        db_feedback = FeedbackModel(
            session_id=session_id,
            topic=feedback.topic,
            summary=feedback.summary,
            sentiment=feedback.sentiment,
        )
        session.add(db_feedback)
        await session.commit()
        await session.refresh(db_feedback)
        return db_feedback
