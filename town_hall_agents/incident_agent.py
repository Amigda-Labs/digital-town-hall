from agents import Agent

incident_agent_instructions = "You are an incident agent. Your job is to convert the conversation in a reporting incident."

incident_agent = Agent(
    name = "Incident Agent",
    instructions = incident_agent_instructions
)