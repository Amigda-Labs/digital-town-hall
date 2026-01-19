# Import all agents first
from town_hall_agents.dialogue_agent import dialogue_agent
from town_hall_agents.triage_agent import triage_agent
from town_hall_agents.insights_agent import insights_agent
from town_hall_agents.conversation_formatter_agent import conversation_formatter_agent

# Set up circular handoffs AFTER all agents are imported
# This breaks the circular import by deferring the handoff setup
# See: docs/circular-imports.md#the-solution
insights_agent.handoffs = [dialogue_agent]
