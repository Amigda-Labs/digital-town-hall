---
title: Handoffs Behind the Scenes
---

# Handoffs Behind the Scenes

This document explains how handoffs work in the Agents SDK and what actually happens when the
model chooses to transfer control from one agent to another.

## What a handoff is

A handoff is a structured way to let an agent delegate control to another agent. The SDK exposes
handoffs as tool-like capabilities so the model can select them in the same way it selects tools.

At a high level:

- You register handoffs on an agent via `Agent(handoffs=[...])`.
- Each handoff is exposed to the model as a function tool named `transfer_to_<agent_name>` by
  default.
- When the model invokes that tool, the SDK switches the active agent and continues the run.

## The Handoff class

The core `Handoff` class is defined in `src/agents/handoffs/__init__.py`:

```python
@dataclass
class Handoff(Generic[TContext, TAgent]):
    """A handoff is when an agent delegates a task to another agent.

    For example, in a customer support scenario you might have a "triage agent" that determines
    which agent should handle the user's request, and sub-agents that specialize in different areas
    like billing, account management, etc.
    """

    tool_name: str
    """The name of the tool that represents the handoff."""

    tool_description: str
    """The description of the tool that represents the handoff."""

    input_json_schema: dict[str, Any]
    """The JSON schema for the handoff input. Can be empty if the handoff does not take an input."""

    on_invoke_handoff: Callable[[RunContextWrapper[Any], str], Awaitable[TAgent]]
    """The function that invokes the handoff.

    The parameters passed are: (1) the handoff run context, (2) the arguments from the LLM as a
    JSON string (or an empty string if ``input_json_schema`` is empty). Must return an agent.
    """

    agent_name: str
    """The name of the agent that is being handed off to."""

    input_filter: HandoffInputFilter | None = None
    """A function that filters the inputs that are passed to the next agent."""

    nest_handoff_history: bool | None = None
    """Override the run-level ``nest_handoff_history`` behavior for this handoff only."""

    strict_json_schema: bool = True
    """Whether the input JSON schema is in strict mode."""

    is_enabled: bool | Callable[[RunContextWrapper[Any], AgentBase[Any]], MaybeAwaitable[bool]] = True
    """Whether the handoff is enabled."""
```

## How handoffs become tool names

The default tool name is generated from the agent name:

```python
@classmethod
def default_tool_name(cls, agent: AgentBase[Any]) -> str:
    return _transforms.transform_string_function_style(f"transfer_to_{agent.name}")

@classmethod
def default_tool_description(cls, agent: AgentBase[Any]) -> str:
    return (
        f"Handoff to the {agent.name} agent to handle the request. "
        f"{agent.handoff_description or ''}"
    )
```

So an agent named `"Billing Agent"` becomes a tool called `transfer_to_billing_agent`.

## Handoffs are serialized as function tools

When the SDK prepares a request to OpenAI, handoffs are converted into function tool definitions.
This happens in `src/agents/models/openai_responses.py`:

```python
@classmethod
def _convert_handoff_tool(cls, handoff: Handoff) -> ToolParam:
    return {
        "name": handoff.tool_name,
        "parameters": handoff.input_json_schema,
        "strict": handoff.strict_json_schema,
        "type": "function",
        "description": handoff.tool_description,
    }
```

And in `src/agents/models/chatcmpl_converter.py` for ChatCompletions:

```python
@classmethod
def convert_handoff_tool(cls, handoff: Handoff[Any, Any]) -> ChatCompletionToolParam:
    return {
        "type": "function",
        "function": {
            "name": handoff.tool_name,
            "description": handoff.tool_description,
            "parameters": handoff.input_json_schema,
            "strict": handoff.strict_json_schema,
        },
    }
```

Handoffs are added to the same tools list as regular function tools:

```python
converted_tools = [Converter.tool_to_openai(tool) for tool in tools] if tools else []

for handoff in handoffs:
    converted_tools.append(Converter.convert_handoff_tool(handoff))
```

**The model doesn't know it's a "handoff"** - it just sees a callable function like
`transfer_to_billing_agent` in its tools list.

## The run loop handles handoff steps

When the model calls a handoff tool, the SDK processes it as a `NextStepHandoff`. This is defined
in `src/agents/_run_impl.py`:

```python
@dataclass
class NextStepHandoff:
    new_agent: Agent[Any]


@dataclass
class SingleStepResult:
    original_input: str | list[TResponseInputItem]
    model_response: ModelResponse
    pre_step_items: list[RunItem]
    new_step_items: list[RunItem]
    next_step: NextStepHandoff | NextStepFinalOutput | NextStepRunAgain
    # ...
```

When a handoff is detected, the run impl returns a `NextStepHandoff`:

```python
return SingleStepResult(
    original_input=original_input,
    model_response=new_response,
    pre_step_items=pre_step_items,
    new_step_items=new_step_items,
    next_step=NextStepHandoff(new_agent),
    tool_input_guardrail_results=[],
    tool_output_guardrail_results=[],
)
```

## The runner switches agents

In `src/agents/run.py`, the main run loop checks for `NextStepHandoff` and switches the current
agent:

```python
elif isinstance(turn_result.next_step, NextStepHandoff):
    # Save the conversation to session if enabled (before handoff)
    if session is not None:
        if not any(
            guardrail_result.output.tripwire_triggered
            for guardrail_result in input_guardrail_results
        ):
            await self._save_result_to_session(
                session,
                [],
                turn_result.new_step_items,
                turn_result.model_response.response_id,
            )
    current_agent = cast(Agent[TContext], turn_result.next_step.new_agent)
    current_span.finish(reset_current=True)
    current_span = None
    should_run_agent_start_hooks = True
```

The key line is `current_agent = turn_result.next_step.new_agent` - this switches execution to
the new agent, and the run loop continues with that agent's instructions and tools.

## History and input shaping

By default, the next agent receives the full conversation history. You can customize this:

- `input_filter` can rewrite or trim the history and new items before the next agent runs.
- `nest_handoff_history` can summarize or nest history to keep prompts smaller.

These controls are useful for large conversations or when you want a specialist agent to focus on
just part of the context.

## Handoffs vs agent-as-tool

`Agent.as_tool()` runs a nested agent and returns control to the original agent. A handoff
transfers control to a new agent and continues the run under that new agent instead of returning.

From `src/agents/agent.py`:

```python
def as_tool(self, ...) -> Tool:
    """Transform this agent into a tool, callable by other agents.

    This is different from handoffs in two ways:
    1. In handoffs, the new agent receives the conversation history. In this tool, the new agent
       receives generated input.
    2. In handoffs, the new agent takes over the conversation. In this tool, the new agent is
       called as a tool, and the conversation is continued by the original agent.
    """
```

## Example: Instructing an agent to handoff

Since handoffs are just tools, you can instruct an agent to use them:

```python
from agents import Agent

billing_agent = Agent(
    name="Billing Agent",
    handoff_description="Handles billing and payment questions",
    instructions="You help users with billing inquiries.",
)

triage_agent = Agent(
    name="Triage Agent",
    instructions="""
    You are a triage agent. Determine what the user needs:
    - If they mention billing, payments, or invoices, transfer to the Billing Agent.
    - Otherwise, help them directly.
    
    Always transfer to the appropriate specialist when relevant.
    """,
    handoffs=[billing_agent],  # Creates a "transfer_to_billing_agent" tool
)
```

The triage agent sees `transfer_to_billing_agent` as a tool and can call it based on instructions.

## Where to look in the code

- `src/agents/handoffs/__init__.py`: defines the `Handoff` object and the `handoff()` helper.
- `src/agents/models/openai_responses.py`: converts handoffs into tool payloads (Responses API).
- `src/agents/models/chatcmpl_converter.py`: converts handoffs for ChatCompletions API.
- `src/agents/_run_impl.py`: defines `NextStepHandoff` and creates handoff step results.
- `src/agents/run.py`: run loop that checks for `NextStepHandoff` and switches agents.
