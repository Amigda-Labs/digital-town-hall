# Understanding `@function_tool` in OpenAI Agents SDK

This document explains how the `@function_tool` decorator works, specifically how it handles parameters and automatically injects context.

## Table of Contents

- [How It Works (High Level)](#how-it-works-high-level)
- [The Two Types of Parameters](#the-two-types-of-parameters)
- [Proof: SDK Source Code](#proof-sdk-source-code)
- [Proof: Official Documentation](#proof-official-documentation)
- [Example](#example)
- [References](#references)

---

## How It Works (High Level)

When you decorate a function with `@function_tool`, the SDK automatically:

1. **Inspects your function signature** using Python's `inspect` module
2. **Checks the first parameter** - if it's `RunContextWrapper` or `ToolContext`, it's marked as "context" and excluded from the LLM
3. **Creates a JSON schema** from all other parameters - this schema is what the LLM sees
4. **At runtime**: The SDK injects the context automatically, and the LLM provides all other arguments

```
┌─────────────────────────────────────────────────────────────────┐
│                   @function_tool decorator                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Your function:                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ async def my_tool(                                        │  │
│  │     ctx: RunContextWrapper[MyContext],  ──┐               │  │
│  │     user_input: str,  ────────────────────┼──┐            │  │
│  │     optional_param: int = 5,  ────────────┼──┼──┐         │  │
│  │ ) -> str:                                 │  │  │         │  │
│  └───────────────────────────────────────────┼──┼──┼─────────┘  │
│                                              │  │  │            │
│                    ┌─────────────────────────┘  │  │            │
│                    │                            │  │            │
│                    ▼                            ▼  ▼            │
│  ┌─────────────────────────┐    ┌────────────────────────────┐  │
│  │   SDK INJECTS           │    │   LLM PROVIDES             │  │
│  │   (hidden from LLM)     │    │   (visible in JSON schema) │  │
│  │                         │    │                            │  │
│  │   • RunContextWrapper   │    │   • user_input: str        │  │
│  │   • ToolContext         │    │   • optional_param: int    │  │
│  └─────────────────────────┘    └────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Two Types of Parameters

| Parameter Type | Who Provides It | Visible to LLM? | Position |
|----------------|-----------------|-----------------|----------|
| `RunContextWrapper[T]` | SDK automatically injects | No | Must be first |
| `ToolContext[T]` | SDK automatically injects | No | Must be first |
| Any other type (`str`, `int`, Pydantic model, etc.) | LLM must provide | Yes (in JSON schema) | Any position after first |

### Key Rules

1. **Context must be the first parameter** - The SDK only checks the first parameter for context types
2. **Context is optional** - You don't have to include it if you don't need it
3. **All other parameters become the tool's schema** - The LLM sees these and must provide values
4. **The LLM infers values from conversation** - When the LLM calls your tool, it extracts the required information from the conversation history

---

## Proof: SDK Source Code

The logic lives in [`agents/function_schema.py`](https://github.com/openai/openai-agents-python/blob/main/src/agents/function_schema.py).

### The Context Check

```python
# From function_schema.py in the function_schema() function

if params:
    first_name, first_param = params[0]
    # Prefer the evaluated type hint if available
    ann = type_hints.get(first_name, first_param.annotation)
    if ann != inspect._empty:
        origin = get_origin(ann) or ann
        if origin is RunContextWrapper or origin is ToolContext:
            takes_context = True  # Mark that the function takes context
        else:
            filtered_params.append((first_name, first_param))
    else:
        filtered_params.append((first_name, first_param))
```

**What this does:**
- Gets the first parameter's type annotation
- Checks if it's `RunContextWrapper` or `ToolContext`
- If yes: sets `takes_context = True` and **excludes** it from `filtered_params`
- If no: adds it to `filtered_params` (will be in JSON schema for LLM)

### The Error Check (Context Must Be First)

```python
# For parameters other than the first, raise error if any use RunContextWrapper or ToolContext.
for name, param in params[1:]:
    ann = type_hints.get(name, param.annotation)
    if ann != inspect._empty:
        origin = get_origin(ann) or ann
        if origin is RunContextWrapper or origin is ToolContext:
            raise UserError(
                f"RunContextWrapper/ToolContext param found at non-first position in function"
                f" {func.__name__}"
            )
    filtered_params.append((name, param))
```

**This enforces that context can ONLY be the first parameter.**

---

## Proof: How the LLM Provides the Other Parameters

Now for the second part: **How does the LLM know what to pass for non-context parameters?**

### The Short Answer

1. The **Runner** accumulates conversation history in an `input` list
2. The **Runner** sends this history + tool schemas to the **LLM**
3. The **LLM** sees the conversation and generates tool arguments as JSON
4. The **SDK** parses the JSON and calls your function

### Proof: Runner Sends Input + Tools to the Model

In [`run.py`](https://github.com/openai/openai-agents-python/blob/main/src/agents/run.py), the `_get_new_response` method makes the actual call to the LLM:

```python
# From run.py - Runner._get_new_response()
new_response = await model.get_response(
    system_instructions=filtered.instructions,
    input=filtered.input,           # <-- THE CONVERSATION HISTORY
    model_settings=model_settings,
    tools=all_tools,                # <-- THE TOOL SCHEMAS
    output_schema=output_schema,
    handoffs=handoffs,
    tracing=get_model_tracing_impl(...),
    previous_response_id=previous_response_id,
    conversation_id=conversation_id,
    prompt=prompt_config,
)
```

### Proof: The Model Interface Requires Both

In [`models/interface.py`](https://github.com/openai/openai-agents-python/blob/main/src/agents/models/interface.py), the `Model` abstract base class defines the contract:

```python
class Model(abc.ABC):
    """The base interface for calling an LLM."""

    @abc.abstractmethod
    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],  # <-- CONVERSATION HISTORY
        model_settings: ModelSettings,
        tools: list[Tool],                       # <-- TOOL SCHEMAS
        output_schema: AgentOutputSchemaBase | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: ResponsePromptParam | None,
    ) -> ModelResponse:
        """Get a response from the model.

        Args:
            system_instructions: The system instructions to use.
            input: The input items to the model, in OpenAI Responses format.
            model_settings: The model settings to use.
            tools: The tools available to the model.
            ...
        """
        pass
```

**This proves that every model implementation MUST receive both:**
1. `input` - The conversation history (list of messages, tool calls, tool outputs)
2. `tools` - The list of available tools with their JSON schemas

### The Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RUNNER                                         │
│                                                                             │
│  1. Accumulates conversation history in `input` list                        │
│  2. Calls model.get_response(input=..., tools=...)                          │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 LLM                                         │
│                                                                             │
│  Sees: "User: I think the park needs more benches..."                       │
│  Sees tool schema: { "conversation": { "type": "string" } }                 │
│                                                                             │
│  Generates: {"conversation": "User: I think the park needs more benches.."} │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SDK (tool.py)                                  │
│                                                                             │
│  1. json.loads(input) → {"conversation": "..."}                             │
│  2. Validate with Pydantic                                                  │
│  3. Call: your_func(ctx, conversation="...")                                │
│                        ↑              ↑                                     │
│                   SDK injects    LLM provided                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Source Code: Tool Invocation

In [`tool.py`](https://github.com/openai/openai-agents-python/blob/main/src/agents/tool.py):

```python
async def _on_invoke_tool_impl(ctx: ToolContext[Any], input: str) -> Any:
    # Parse the JSON from the LLM
    json_data: dict[str, Any] = json.loads(input) if input else {}
    
    # Validate and convert to function arguments
    parsed = schema.params_pydantic_model(**json_data)
    args, kwargs_dict = schema.to_call_args(parsed)
    
    # Call with or without context
    if schema.takes_context:
        result = await the_func(ctx, *args, **kwargs_dict)  # Context injected
    else:
        result = await the_func(*args, **kwargs_dict)       # No context
```

**The LLM infers argument values from the conversation it has seen.** If you define a parameter like `client_name: str`, the LLM will look through the conversation to find the client's name and pass it.

### Deep Dive: Conversation History Management

For a detailed explanation of:
- How the `input` list is stored and managed
- The `to_input_list()` method
- Storage options (temporary vs persistent)
- Expiration and TTL settings
- Sessions for automatic history management

**See: [`docs/conversation-history-management.md`](./conversation-history-management.md)**

---

## Proof: Official Documentation

From the [OpenAI Agents SDK Tools Documentation](https://openai.github.io/openai-agents-python/tools/):

> **"Functions can optionally take the `context` (must be the first argument)."**

The documentation also shows two example functions - one without context, one with:

```python
# WITHOUT context - only LLM-provided params
@function_tool
async def fetch_weather(location: Location) -> str:
    """Fetch the weather for a given location."""
    return "sunny"

# WITH context - ctx is first, then LLM-provided params
@function_tool
def read_file(ctx: RunContextWrapper[Any], path: str, directory: str | None = None) -> str:
    """Read the contents of a file."""
    return "<file contents>"
```

The documentation then shows the **generated JSON schema** for `read_file`, proving that `ctx` is excluded:

```json
{
  "properties": {
    "path": {
      "description": "The path to the file to read.",
      "type": "string"
    },
    "directory": {
      "anyOf": [{"type": "string"}, {"type": "null"}],
      "default": null,
      "description": "The directory to read the file from."
    }
  },
  "required": ["path"]
}
```

**Notice: `ctx` is NOT in the schema! Only `path` and `directory` are visible to the LLM.**

---

## Example

Here's a complete example from this codebase:

### The Tool Definition

```python
# town_hall_agents/feedback_formatter_agent.py

from agents import Agent, RunContextWrapper, function_tool, Runner
from core.models import Feedback
from core.context import TownHallContext, AgentStage

feedback_formatter_agent = Agent(
    name="Feedback Formatter Agent",
    instructions=feedback_formatter_instructions,
    output_type=Feedback
)

@function_tool
async def feedback_formatter_tool(
    ctx: RunContextWrapper[TownHallContext],  # SDK injects this
    conversation: str,                         # LLM provides this
) -> Feedback:
    """
    Format feedback from the conversation.
    Use this tool for formatting feedback (i.e. user recommendations, suggestions, complaints).
    
    Args:
        conversation: The conversation text to extract feedback from.
    """
    # Update stage
    ctx.context.agent_stage = AgentStage.FEEDBACK_FORMATTING
    
    # Run nested agent
    result = await Runner.run(
        starting_agent=feedback_formatter_agent,
        input=conversation,
        context=ctx.context
    )
    
    # Store in context
    ctx.context.feedback = result.final_output
    ctx.context.feedback_processed = True
    
    return result.final_output
```

### How It's Used

```python
# town_hall_agents/conversation_format_coordinator_agent.py

from agents import Agent
from town_hall_agents.feedback_formatter_agent import feedback_formatter_tool

conversation_format_coordinator_agent = Agent(
    name="Conversation Format Coordinator Agent",
    instructions=conversation_format_coordinator_agent_instructions,
    tools=[feedback_formatter_tool, ...]  # Just pass the decorated function
)
```

### What Happens at Runtime

1. `conversation_format_coordinator_agent` receives the conversation history through handoffs
2. Its LLM decides to call `feedback_formatter_tool`
3. The LLM generates: `{"conversation": "User said: I think the park needs more benches..."}`
4. SDK automatically injects `ctx` with the shared `TownHallContext`
5. Your tool runs, stores data in context, and returns the result

---

## References

### Official Documentation
- [OpenAI Agents SDK - Tools](https://openai.github.io/openai-agents-python/tools/)
- [OpenAI Agents SDK - Context Management](https://openai.github.io/openai-agents-python/context/)
- [OpenAI Agents SDK - Running Agents](https://openai.github.io/openai-agents-python/running_agents/)
- [OpenAI Agents SDK - Sessions](https://openai.github.io/openai-agents-python/sessions/)

### Source Code
- [function_schema.py](https://github.com/openai/openai-agents-python/blob/main/src/agents/function_schema.py) - Parameter inspection and context detection
- [tool.py](https://github.com/openai/openai-agents-python/blob/main/src/agents/tool.py) - Tool invocation and JSON argument parsing
- [run.py](https://github.com/openai/openai-agents-python/blob/main/src/agents/run.py) - Runner and conversation history accumulation
- [run_context.py](https://github.com/openai/openai-agents-python/blob/main/src/agents/run_context.py) - `RunContextWrapper` definition
- [tool_context.py](https://github.com/openai/openai-agents-python/blob/main/src/agents/tool_context.py) - `ToolContext` definition

### Related Documentation in This Project
- [`docs/conversation-history-management.md`](./conversation-history-management.md) - How conversation history is stored, persisted, and managed
- [`docs/hooks-vs-nested-runs.md`](./hooks-vs-nested-runs.md) - Comparison of approaches for managing state

### Related Code in This Project
- [`core/context.py`](../core/context.py) - The `TownHallContext` class
- [`town_hall_agents/feedback_formatter_agent.py`](../town_hall_agents/feedback_formatter_agent.py) - Example using explicit `Runner.run()`
- [`town_hall_agents/incident_formatter_agent.py`](../town_hall_agents/incident_formatter_agent.py) - Example using `as_tool()`
