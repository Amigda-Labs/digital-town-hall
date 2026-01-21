from agents import Agent
from core.models import Incident


incident_agent_instructions = """
You are an incident agent. Your job is to convert the conversation in a reporting incident.
"""

incident_formatter_agent = Agent(
    name = "Incident Formatter Agent",
    instructions = incident_agent_instructions,
    output_type = Incident
)

incident_formatter_tool = incident_formatter_agent.as_tool(
    tool_name="incident_formatter_tool", #No spaces allowed
    tool_description="Use this tool for formatting incidents"
)