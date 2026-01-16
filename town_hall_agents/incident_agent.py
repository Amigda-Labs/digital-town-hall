from agents import Agent
from pydantic import BaseModel
from datetime import datetime

class Incident(BaseModel):
    incident_type: str
    description: str
    date_of_occurence: datetime | None
    locaiton: str
    person_involved: str
    reporter_name: str | None
    severity_level: int

incident_agent_instructions = """
You are an incident agent. Your job is to convert the conversation in a reporting incident.
"""

incident_agent = Agent(
    name = "Incident Agent",
    instructions = incident_agent_instructions,
    output_type = Incident
)