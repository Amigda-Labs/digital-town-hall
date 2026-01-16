from agents import Agent
from town_hall_agents.incident_agent import incident_agent
from town_hall_agents.feedback_formatter_agent import feedback_formatter_agent
from town_hall_agents.insights_agent import insights_agent

triage_agent_instructions = """
You are a triage agent. Your job is to assess if the conversation passed to you is going to the `incident_agent`, `insights_agent`, `feedback_formatter_agent`
You are expected to receive a user message,
If the message is about incidents, pass the message to the incident agent.
If the message is a suggestion or a feedback, pass the message to the feedback_formatter_agent.
If the message is about asking insights, pass the message/inquiry to the insights_agent.
"""

triage_agent = Agent(
    name = "Triage Agent",
    instructions=triage_agent_instructions,
    handoffs=[incident_agent, feedback_formatter_agent, insights_agent]
)