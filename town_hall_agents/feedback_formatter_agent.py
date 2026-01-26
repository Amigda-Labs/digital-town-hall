from agents import Agent
from core.models import Feedback


feedback_formatter_instructions = """
You are a feedback formatter agent. Your role is to convert the customer's feedback into a structured format.
"""

feedback_formatter_agent = Agent(
    name="Feedback Formatter Agent",
    instructions=feedback_formatter_instructions,
    output_type=Feedback
)

feedback_formatter_tool = feedback_formatter_agent.as_tool(
    tool_name="feedback_formatter_tool",
    tool_description="Use this tool for formatting Feedbacks",
)
