"""
Lifecycle hooks for agent tool execution.

This module implements Approach B from docs/hooks-vs-nested-runs.md:
- Tools are defined simply with as_tool()
- State management (context storage, logging, database prep) is handled in hooks
- Hooks are attached to the parent agent (conversation_format_coordinator_agent)
"""
from typing import Any
from agents.lifecycle import AgentHooks
from agents import RunContextWrapper
from core.context import TownHallContext, AgentStage
from core.models import Feedback, Incident


class ConversationFormatterHooks(AgentHooks):
    """
    Hooks for the Conversation Format Coordinator Agent.
    
    Captures tool outputs and stores them in context for:
    - feedback_formatter_tool
    - incident_formatter_tool
    """
    
    async def on_tool_start(
        self,
        context: RunContextWrapper[TownHallContext],
        agent,
        tool
    ):
        """Called before a tool is executed."""
        print(f"...Running {tool.name}")
    
    async def on_tool_end(
        self,
        context: RunContextWrapper[TownHallContext],
        agent,
        tool,
        result: Any
    ):
        """
        Called after a tool completes.
        Stores the result in context and prepares for database upload.
        
        Note: When using as_tool() with output_type, result is already the Pydantic model.
        """
        if tool.name == "feedback_formatter_tool":
            # Update stage
            context.context.agent_stage = AgentStage.FEEDBACK_FORMATTING
            
            # Result is already a Feedback model when using as_tool() with output_type
            context.context.feedback = result
            context.context.feedback_processed = True
            print("Feedback is now stored in context")
            
            # TODO: Persist feedback to database when persistence layer is ready
            print("Database persistence point: feedback ready for upload")
        
        elif tool.name == "incident_formatter_tool":
            # Update stage
            context.context.agent_stage = AgentStage.INCIDENT_FORMATTING
            
            # Result is already an Incident model when using as_tool() with output_type
            context.context.incident = result
            context.context.incident_processed = True
            print("Incident is now stored in context")
            
            # TODO: Persist incident to database when persistence layer is ready
            print("Database persistence point: incident ready for upload")
