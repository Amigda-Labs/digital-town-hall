# Agents as Tools: Understanding `as_tool`

This guide explains how the `as_tool` method works in the OpenAI Agents SDK, transforming an `Agent` into a callable tool that other agents can invoke. Before diving into the implementation, we'll review Python decorators since `as_tool` heavily relies on the `@function_tool` decorator.

## Table of Contents

1. [Python Decorators Refresher](#python-decorators-refresher)
2. [The `@function_tool` Decorator](#the-function_tool-decorator)
3. [How `as_tool` Works](#how-as_tool-works)
4. [Context Management](#context-management)
5. [Hook Support](#hook-support)
6. [Streaming Support](#streaming-support)
7. [Difference from Handoffs](#difference-from-handoffs)
8. [Usage Examples](#usage-examples)

---

## Python Decorators Refresher

Decorators are a powerful Python feature that allows you to modify or extend the behavior of functions or classes without changing their source code. They use the `@` syntax and are essentially functions that take another function as input and return a new function.

### Basic Decorator Pattern

```python
def my_decorator(func):
    def wrapper(*args, **kwargs):
        print("Before the function call")
        result = func(*args, **kwargs)
        print("After the function call")
        return result
    return wrapper

@my_decorator
def say_hello(name):
    print(f"Hello, {name}!")

# When you call say_hello("World"), it actually calls wrapper("World")
say_hello("World")
# Output:
# Before the function call
# Hello, World!
# After the function call
```

### Decorators with Arguments

When a decorator needs its own arguments, you need an extra layer of nesting:

```python
def repeat(times):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for _ in range(times):
                result = func(*args, **kwargs)
            return result
        return wrapper
    return decorator

@repeat(times=3)
def greet(name):
    print(f"Hi, {name}!")

greet("Alice")
# Output:
# Hi, Alice!
# Hi, Alice!
# Hi, Alice!
```

### How `@decorator(args)` Works

The syntax `@repeat(times=3)` is equivalent to:

```python
def greet(name):
    print(f"Hi, {name}!")

greet = repeat(times=3)(greet)
```

This two-step process is:
1. `repeat(times=3)` returns the actual decorator function
2. That decorator is applied to `greet`

### Decorators Returning Different Types

Decorators don't have to return functions—they can return any object:

```python
def make_tool(name):
    def decorator(func):
        # Returns a Tool object, not a function
        return Tool(name=name, handler=func)
    return decorator

@make_tool(name="calculator")
def add(a, b):
    return a + b

# add is now a Tool object, not a function
print(type(add))  # <class 'Tool'>
```

This pattern is exactly what `@function_tool` does—it transforms a function into a `FunctionTool` object.

---

## The `@function_tool` Decorator

The `@function_tool` decorator (defined in `src/agents/tool.py`) transforms a Python function into a `FunctionTool` that LLMs can call. Here's what it does:

### Core Functionality

```python
@function_tool(
    name_override="my_tool",           # Custom tool name (optional)
    description_override="Does X",      # Custom description (optional)
    failure_error_function=handler,     # Error handler (optional)
    strict_mode=True,                   # Strict JSON schema (default True)
    is_enabled=True,                    # Enable/disable the tool
)
async def my_function(context: ToolContext, param: str) -> str:
    """This docstring becomes the tool description if not overridden."""
    return f"Processed: {param}"
```

### What Happens Under the Hood

1. **Schema Generation**: Parses the function signature to create a JSON schema for the LLM
2. **Docstring Parsing**: Extracts description and parameter info from the docstring
3. **Context Injection**: Automatically passes `ToolContext` if the first parameter expects it
4. **Error Handling**: Wraps execution to catch errors and format them for the LLM
5. **Async Support**: Handles both sync and async functions

### The Resulting `FunctionTool`

```python
@dataclass
class FunctionTool:
    name: str                    # Tool name for the LLM
    description: str             # What the tool does
    params_json_schema: dict     # JSON schema of parameters
    on_invoke_tool: Callable     # The actual function to call
    is_enabled: bool | Callable  # Whether the tool is available
    strict_json_schema: bool     # Whether to enforce strict schema
    failure_error_function: ...  # How to handle errors
```

---

## How `as_tool` Works

The `as_tool` method (lines 405-538 in `agent.py`) uses `@function_tool` internally to wrap an agent execution in a tool interface.

Reference: https://github.com/openai/openai-agents-python/blob/main/src/agents/agent.py#L405

### Method Signature

```python
def as_tool(
    self,
    tool_name: str | None,
    tool_description: str | None,
    custom_output_extractor: Callable[[RunResult | RunResultStreaming], Awaitable[str]] | None = None,
    is_enabled: bool | Callable[[RunContextWrapper[Any], AgentBase[Any]], MaybeAwaitable[bool]] = True,
    on_stream: Callable[[AgentToolStreamEvent], MaybeAwaitable[None]] | None = None,
    run_config: RunConfig | None = None,
    max_turns: int | None = None,
    hooks: RunHooks[TContext] | None = None,
    previous_response_id: str | None = None,
    conversation_id: str | None = None,
    session: Session | None = None,
    failure_error_function: ToolErrorFunction | None = default_tool_error_function,
) -> Tool:
```

### The Transformation Process

Here's what happens inside `as_tool`:

```python
def as_tool(self, tool_name, tool_description, ...):
    
    # 1. Create an inner function that will run the agent
    @function_tool(
        name_override=tool_name or transform_to_snake_case(self.name),
        description_override=tool_description or "",
        is_enabled=is_enabled,
        failure_error_function=failure_error_function,
    )
    async def run_agent(context: ToolContext, input: str) -> Any:
        from .run import Runner
        
        # 2. Run the agent with the provided input
        if on_stream is not None:
            # Streaming path
            run_result = Runner.run_streamed(
                starting_agent=self,
                input=input,
                context=context.context,  # Pass through the context
                run_config=run_config,
                max_turns=max_turns,
                hooks=hooks,
                ...
            )
            # Handle streaming events...
        else:
            # Non-streaming path
            run_result = await Runner.run(
                starting_agent=self,
                input=input,
                context=context.context,
                run_config=run_config,
                max_turns=max_turns,
                hooks=hooks,
                ...
            )
        
        # 3. Extract and return the output
        if custom_output_extractor:
            return await custom_output_extractor(run_result)
        return run_result.final_output
    
    # 4. Return the FunctionTool
    return run_agent
```

### The Tool's Interface

From the LLM's perspective, the tool looks like:

```json
{
  "name": "translate_to_spanish",
  "description": "Translate the user's message to Spanish",
  "parameters": {
    "type": "object",
    "properties": {
      "input": {
        "type": "string"
      }
    },
    "required": ["input"]
  }
}
```

The LLM calls this tool with an `input` string, and the nested agent processes it.

---

## Context Management

Context flows seamlessly from the parent agent to the nested agent.

### The Context Chain

```
┌────────────────────────────────────────────────────────────┐
│  Parent Agent Run                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  RunContextWrapper                                  │   │
│  │  ├── context: YourCustomContext      ←───────────────┐  │  
│  │  └── usage: Usage                                   ││  │
│  └─────────────────────────────────────────────────────┘│  │
│                           │                            ││  │
│                           ▼                            ││  │
│  ┌─────────────────────────────────────────────────────┐│  │
│  │  Tool Invocation                                    ││  │
│  │  ┌───────────────────────────────────────────────┐  ││  │
│  │  │  ToolContext (extends RunContextWrapper)      │  ││  │
│  │  │  ├── context: YourCustomContext ──────────────┼───┘  │
│  │  │  ├── tool_name: "translate_to_spanish"        │  │   │
│  │  │  ├── tool_call_id: "call_abc123"              │  │   │
│  │  │  └── tool_call: ResponseFunctionToolCall      │  │   │
│  │  └───────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                │
│                           ▼                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Nested Agent Run                                   │   │
│  │  Runner.run(                                        │   │
│  │      starting_agent=nested_agent,                   │   │
│  │      input="Hello",                                 │   │
│  │      context=context.context,  ← Same object!       │   │
│  │  )                                                  │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

### Key Points

1. **Shared Context Object**: The same `context` object is passed to the nested agent
2. **Mutable State**: Changes to the context in the nested run are visible to the parent
3. **Usage Tracking**: Each run has its own `Usage` tracking, but shares the context

### ToolContext Definition

```python
@dataclass
class ToolContext(RunContextWrapper[TContext]):
    """The context of a tool call."""

    tool_name: str        # Name of the tool being invoked
    tool_call_id: str     # Unique ID of this tool call
    tool_arguments: str   # Raw JSON arguments string
    tool_call: Optional[ResponseFunctionToolCall]  # Full tool call object
```

---

## Hook Support

`as_tool` fully supports the SDK's hook system, allowing you to observe and react to lifecycle events in the nested agent run.

### Two Levels of Hooks

#### 1. Run-Level Hooks (via `as_tool` parameter)

```python
from agents import Agent, RunHooks, RunContextWrapper

class MyRunHooks(RunHooks):
    async def on_agent_start(self, context, agent):
        print(f"Nested agent {agent.name} starting")
    
    async def on_agent_end(self, context, agent, output):
        print(f"Nested agent {agent.name} finished with: {output}")
    
    async def on_tool_start(self, context, agent, tool):
        print(f"Nested agent calling tool: {tool.name}")

# Apply hooks to the nested run
spanish_tool = spanish_agent.as_tool(
    tool_name="translate_to_spanish",
    tool_description="Translate to Spanish",
    hooks=MyRunHooks(),  # These hooks fire during the nested run
)
```

#### 2. Agent-Level Hooks (via `agent.hooks`)

```python
from agents import Agent, AgentHooks

class SpanishAgentHooks(AgentHooks):
    async def on_start(self, context, agent):
        print("Spanish agent starting its work")
    
    async def on_end(self, context, agent, output):
        print(f"Spanish agent produced: {output}")

spanish_agent = Agent(
    name="spanish_agent",
    instructions="Translate to Spanish",
    hooks=SpanishAgentHooks(),  # Fires when this specific agent runs
)
```

### Available Hook Methods

| Hook | When it Fires |
|------|---------------|
| `on_agent_start` | Before an agent begins processing |
| `on_agent_end` | When an agent produces final output |
| `on_llm_start` | Before calling the LLM |
| `on_llm_end` | After LLM response received |
| `on_tool_start` | Before invoking a tool |
| `on_tool_end` | After tool returns |
| `on_handoff` | When handing off to another agent |

---

## Streaming Support

The `on_stream` callback enables real-time streaming of events from the nested agent.

### Using `on_stream`

```python
from agents import Agent, AgentToolStreamEvent

async def handle_stream(event: AgentToolStreamEvent):
    stream_event = event["event"]
    current_agent = event["agent"]
    tool_call = event["tool_call"]
    
    # React to different event types
    if hasattr(stream_event, 'data'):
        print(f"Stream data from {current_agent.name}: {stream_event.data}")

billing_tool = billing_agent.as_tool(
    tool_name="billing_agent",
    tool_description="Handle billing questions",
    on_stream=handle_stream,  # Callback for each stream event
)
```

### Stream Event Structure

```python
class AgentToolStreamEvent(TypedDict):
    event: StreamEvent              # The actual streaming event
    agent: Agent[Any]               # Current agent emitting the event
    tool_call: ResponseFunctionToolCall | None  # The originating tool call
```

### How Streaming Works Internally

When `on_stream` is provided:

1. `Runner.run_streamed()` is used instead of `Runner.run()`
2. Events are consumed via `async for event in run_result.stream_events()`
3. Each event is wrapped in `AgentToolStreamEvent` with agent context
4. Events are dispatched to your callback via an async queue (non-blocking)

---

## Difference from Handoffs

| Aspect | `as_tool` | Handoffs |
|--------|-----------|----------|
| **Input** | LLM generates input string | Receives full conversation history |
| **Control Flow** | Returns to original agent | New agent takes over |
| **Use Case** | Delegation for specific tasks | Complete transfer of responsibility |
| **Output** | Tool result returned to caller | Handoff agent continues conversation |

### Visual Comparison

**as_tool Pattern:**
```
User → Agent A → [calls Agent B as tool] → Agent B runs → result → Agent A continues → Response
```

**Handoff Pattern:**
```
User → Agent A → [handoff to Agent B] → Agent B takes over → Response
```

---

## Usage Examples

### Basic Translation Agents

```python
from agents import Agent, Runner

# Create specialist agents
spanish_agent = Agent(
    name="spanish_agent",
    instructions="You translate the user's message to Spanish",
)

french_agent = Agent(
    name="french_agent",
    instructions="You translate the user's message to French",
)

# Create orchestrator with agents as tools
orchestrator = Agent(
    name="orchestrator",
    instructions="You are a translation agent. Use the provided tools to translate.",
    tools=[
        spanish_agent.as_tool(
            tool_name="translate_to_spanish",
            tool_description="Translate the user's message to Spanish",
        ),
        french_agent.as_tool(
            tool_name="translate_to_french",
            tool_description="Translate the user's message to French",
        ),
    ],
)

# Run
result = await Runner.run(orchestrator, "Translate 'Hello' to Spanish and French")
```

### Conditional Tool Enabling

```python
from dataclasses import dataclass
from agents import Agent, RunContextWrapper, AgentBase

@dataclass
class AppContext:
    user_language_preferences: list[str]

def is_language_enabled(ctx: RunContextWrapper[AppContext], agent: AgentBase) -> bool:
    # Only enable Spanish if user has it in preferences
    return "spanish" in ctx.context.user_language_preferences

spanish_tool = spanish_agent.as_tool(
    tool_name="translate_to_spanish",
    tool_description="Translate to Spanish",
    is_enabled=is_language_enabled,  # Dynamically enabled based on context
)
```

### Custom Output Extraction

```python
async def extract_summary(result) -> str:
    """Extract just a summary from the agent's full output."""
    output = result.final_output
    # Custom processing
    return f"Summary: {output[:100]}..."

research_tool = research_agent.as_tool(
    tool_name="research",
    tool_description="Research a topic",
    custom_output_extractor=extract_summary,
)
```

### Full Configuration Example

```python
from agents import Agent, RunConfig, RunHooks, Session

tool = specialist_agent.as_tool(
    tool_name="specialist",
    tool_description="Handle specialized queries",
    custom_output_extractor=my_extractor,
    is_enabled=True,
    on_stream=handle_stream,
    run_config=RunConfig(model="gpt-4.1"),
    max_turns=5,
    hooks=MyRunHooks(),
    session=my_session,
    failure_error_function=custom_error_handler,
)
```

---

## Summary

The `as_tool` method is a powerful pattern for composing agents:

1. **Transforms agents into tools** using the `@function_tool` decorator
2. **Shares context** between parent and nested agent runs
3. **Supports hooks** at both run and agent levels
4. **Enables streaming** via the `on_stream` callback
5. **Differs from handoffs** by keeping control with the original agent

This pattern enables sophisticated multi-agent architectures where a coordinator agent can delegate specific tasks to specialist agents while maintaining overall conversation control.
