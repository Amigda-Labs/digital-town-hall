from agents import Agent, RunContextWrapper, function_tool
from core.models import Feedback
from core.context import TownHallContext
from agents import Runner
from core.context import AgentStage


feedback_formatter_instructions = """
You are a feedback formatter agent. Your role is to convert the customer's feedback into a structured format.
"""

feedback_formatter_agent = Agent(
    name = "Feedback Formatter Agent",
    instructions = "feedback_formatter_instructions",
    output_type=Feedback
)


@function_tool
async def feedback_formatter_tool(
    ctx: RunContextWrapper[TownHallContext],
    conversation: str,
) -> Feedback:
    """
    Format feedback from the conversation.
    Use this tool for formatting feedback (i.e. user recommendations, suggestions, complaints).
    
    Args:
        conversation: The conversation text to extract feedback from.
    """
    print("...Running Feedback formatter tool")
    # Update stage (optional but good for tracking)
    ctx.context.agent_stage = AgentStage.FEEDBACK_FORMATTING

    # Run the nested agent with Runner.run()
    result = await Runner.run(
        starting_agent=feedback_formatter_agent,
        input=conversation,
        context=ctx.context  # Pass through the shared context
    )

    # Get the structured feedback output
    feedback = result.final_output

    # Store in context
    ctx.context.feedback = feedback
    ctx.context.feedback_processed = True
    print("Feedback is Now stored in context")

    # TODO: Persist feedback to database when persistence layer is ready
    print("Database persistence point: feedback ready for upload")


    return feedback

# feedback_formatter_tool = feedback_formatter_agent.as_tool(
#    tool_name="feedback_formatter_tool", #No spaces allowed
#    tool_description="Use this tool for formatting Feedbacks",
#)
