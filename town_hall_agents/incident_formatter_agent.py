from agents import Agent, RunContextWrapper, function_tool
from core.models import Incident
from core.context import TownHallContext
from agents import Runner
from core.context import AgentStage
from core.database import save_incident


incident_agent_instructions = """
You are an incident agent. Your job is to convert the conversation in a reporting incident.
"""

incident_formatter_agent = Agent(
    name = "Incident Formatter Agent",
    instructions = incident_agent_instructions,
    output_type = Incident
)


@function_tool
async def incident_formatter_tool(
    ctx: RunContextWrapper[TownHallContext],
    conversation: str,
) -> Incident:
    """
    Format incident from the conversation.
    Use this tool for formatting incidents.
    
    Args:
        conversation: The conversation text to extract incident from.
    """
    print("...Running Incident formatter tool")
    # Update stage (optional but good for tracking)
    ctx.context.agent_stage = AgentStage.INCIDENT_FORMATTING

    # Run the nested agent with Runner.run()
    result = await Runner.run(
        starting_agent=incident_formatter_agent,
        input=conversation,
        context=ctx.context  # Pass through the shared context
    )

    # Get the structured incident output
    incident = result.final_output

    # Store in context
    ctx.context.incident = incident
    ctx.context.incident_processed = True
    print("Incident is now stored in context")
    
    # Persist incident to database (session_id passed separately as metadata)
    db_incident = await save_incident(incident, session_id=ctx.context.session_id)
    print(f"Incident saved to database with ID: {db_incident.id}")

    return incident

# incident_formatter_tool = incident_formatter_agent.as_tool(
#     tool_name="incident_formatter_tool", #No spaces allowed
#     tool_description="Use this tool for formatting incidents"
# )