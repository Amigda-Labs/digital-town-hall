from agents import Agent
from pydantic import BaseModel
from typing import Literal

class Conversation(BaseModel):
    #Topics
    topics: list[str]
    primary_topic: str
    #Analytical Signals
    topic_shift_count: int
    turn_count: int
    # Interventions
    handoff_count: int 
    #Category
    conversation_type: Literal["incident","feedback","inquiry","other"]
    #Sentiments
    sentiment_start: float
    sentiment_end: float
    sentiment_trend: float #Quantitative
    sentiment_direction: Literal["up", "down", "flat"] #Qualitative
    #Outcome
    resolved: bool

    # To be added soon:
    # avg_response_time
    # message_count


conversation_formatter_agent_instructions = """
You are a conversation formatter agent. Your goal is to format the conversation into a structured format.
"""

conversation_formatter_agent = Agent(
    name = "Conversation Formatter Agent",
    instructions = conversation_formatter_agent_instructions,
    output_type = Conversation
)
