from agents import Agent
from pydantic import BaseModel

class Feedback(BaseModel):
    topic: str
    summary: str
    sentiment: str # e.g. "positive", "neutral", "negative"


feedback_formatter_instructions = """
You are a feedback formatter agent. Your role is to convert the customer's feedback into a structured format.
"""

feedback_formatter_agent = Agent(
    name = "Feedback Formatter Agent",
    instructions = "feedback_formatter_instructions",
    output_type=Feedback
)