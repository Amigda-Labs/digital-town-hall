from agents import Agent

triage_agent_instructions = "You are a triage agent. Your job is to assess if the conversation passed to you is going to the `incident_agent`, `insights_agent`, `feedback_formatter_agent`" 

triage_agent = Agent(
    name = "Triage Agent",
    instructions=triage_agent_instructions
)