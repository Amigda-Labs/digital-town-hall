from enum import Enum
from tkinter import N
from token import OP
from typing import Optional
from pydantic import BaseModel
from core.models import Incident, Feedback, Conversation


class AgentStage(str, Enum):
    DIALOGUE = "dialogue"
    TRIAGE = "triage"
    INSIGHTS = "insights"
    CONVERSATION_FORMATTING = "conversation_formatting"
    INCIDENT_FORMATTING = "incident_formatting"
    FEEDBACK_FORMATTING = "feedback_formatting"

class TownHallContext(BaseModel):
    # Stage Tracking (for prompt prefixes and for special cases)
    agent_stage: AgentStage = AgentStage.DIALOGUE

    # Typed outputs (for database upload)
    incident: Optional[Incident] = None
    feedback: Optional[Feedback] = None
    conversation: Optional[Feedback] = None
    insights: Optional[str] = None

    # Processing flag (prevents duplicate processing, enables multi-topic detection)
    # These flags track if an incident/feedback has been extracted and stored
    # The converation_formatter_agent still analyzes content but checks these flags
    # to avoid re-processing the same incident/feedback
    incident_processed: bool = False
    feedback_processed: bool = False

    

