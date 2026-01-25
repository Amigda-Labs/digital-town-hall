# This will be the agent in charge of summarizing the conversation between the dialogue agent and the user.

from agents import Agent
from core.models import Conversation

conversation_summary_agent_instructions = """
You are a conversation summary agent.
Your job is to summarize the stored conversation.
"""

conversation_summarizer_agent = Agent(
    name = "Conversation Summarizer Agent",
    instructions = conversation_summary_agent_instructions,
    output_type= Conversation,
)

conversation_summarizer_tool = conversation_summarizer_agent.as_tool(
    tool_name = "conversation_summarizer_tool", #No Spaces Allowed
    tool_description="Use this tool to summarize the conversation between the dialogue agent and the user"
)