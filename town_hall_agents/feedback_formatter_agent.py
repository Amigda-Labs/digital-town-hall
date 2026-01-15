from agents import Agent

feedback_formatter_instructions = "You are a feedback formatter agent. Your role is to convert the customer's feedback into a structured format."

feedback_formatter_agent = Agent(
    name = "Feedback Formatter Agent",
    instructions = "feedback_formatter_instructions" 
)