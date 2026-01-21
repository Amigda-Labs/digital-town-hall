# Managing State in OpenAI Agents SDK: Two Approaches

This document explains two valid approaches for invoking agents as tools and managing shared context. Both approaches create nested runs internally - the choice is about code style and separation of concerns.

Reference Link: https://github.com/openai/openai-agents-python/issues/2348

## Table of Contents

- [Key Insight: Both Create Nested Runs](#key-insight-both-create-nested-runs)
- [Approach A: Explicit Runner.run() in function_tool](#approach-a-explicit-runnerrun-in-function_tool)
- [Approach B: agent.as_tool() with Hooks](#approach-b-agentas_tool-with-hooks)
- [Context Sharing: How It Works](#context-sharing-how-it-works)
- [Hook Types Reference](#hook-types-reference)
- [Practical Examples](#practical-examples)
- [When to Use What](#when-to-use-what)

---

## Key Insight: Both Create Nested Runs

Looking at the [source code for `as_tool()`](https://github.com/openai/openai-agents-python/blob/main/src/agents/agent.py#L405), we can see that `agent.as_tool()` is syntactic sugar that internally calls `Runner.run()`:

```python
# Inside as_tool() - simplified
@function_tool(...)
async def run_agent(context: ToolContext, input: str) -> Any:
    run_result = await Runner.run(
        starting_agent=self,
        input=input,
        context=context.context,  # Context IS passed!
        # ...
    )
    return run_result.final_output
```

**Key takeaways:**
1. Both approaches create nested runs (traces within traces)
2. Both share context when passed correctly
3. The difference is about **code style** and **separation of concerns**, not about avoiding nested runs

---

## Approach A: Explicit Runner.run() in function_tool

Write the nested run explicitly, giving you full control over the process.

```python
from agents import function_tool, RunContextWrapper, Runner
from core.context import TownHallContext, AgentStage
from core.models import Incident

@function_tool
async def incident_formatter_tool(
    ctx: RunContextWrapper[TownHallContext],
    conversation: str
) -> Incident:
    """
    Format an incident from the conversation.
    Use this tool for formatting incidents (i.e. lost items, anomalies, violations, crime)
    """
    # Update stage
    ctx.context.agent_stage = AgentStage.INCIDENT_FORMATTING
    
    # Explicit nested run - context is passed manually
    result = await Runner.run(
        starting_agent=incident_formatter_agent,
        input=conversation,
        context=ctx.context  # Must pass context explicitly
    )
    
    # Capture output and update context
    incident = result.final_output
    ctx.context.incident = incident
    ctx.context.incident_processed = True
    
    return incident
```

### Pros
- **Explicit control flow**: Everything is visible in one place
- **Self-contained**: The tool handles its own state management
- **Easy to understand**: Reading the code shows exactly what happens

### Cons
- **More boilerplate**: You write the Runner.run() call yourself
- **Mixed concerns**: Business logic and state management are in the same place

---

## Approach B: agent.as_tool() with Hooks

Use the SDK's convenience method and separate state management into hooks.

### Step 1: Create the tool using as_tool()

```python
from agents import Agent
from core.models import Incident

incident_formatter_agent = Agent(
    name="Incident Formatter Agent",
    instructions=incident_agent_instructions,
    output_type=Incident
)

# as_tool() creates a function_tool that calls Runner.run() internally
incident_formatter_tool = incident_formatter_agent.as_tool(
    tool_name="incident_formatter_tool",
    tool_description="Use this tool for formatting incidents"
)
```

### Step 2: Capture output using parent agent's hooks

```python
from agents.lifecycle import AgentHooks
from agents import RunContextWrapper
from core.context import TownHallContext, AgentStage
from typing import Any

class ConversationFormatterHooks(AgentHooks):
    async def on_tool_end(
        self, 
        wrapper: RunContextWrapper[TownHallContext], 
        agent, 
        tool, 
        result: Any
    ):
        """Capture formatter outputs and store in context."""
        if tool.name == "incident_formatter_tool":
            wrapper.context.incident = result
            wrapper.context.incident_processed = True
            print(f"✅ Incident captured: {result}")
        
        elif tool.name == "feedback_formatter_tool":
            wrapper.context.feedback = result
            wrapper.context.feedback_processed = True
            print(f"✅ Feedback captured: {result}")

# Attach hooks to the parent agent
conversation_formatter_agent.hooks = ConversationFormatterHooks()
```

### Alternative: Use nested agent's hooks

```python
class IncidentFormatterHooks(AgentHooks):
    async def on_end(self, wrapper: RunContextWrapper[TownHallContext], agent, run_item):
        """Update context when the formatter agent completes."""
        wrapper.context.incident = run_item.output
        wrapper.context.incident_processed = True
        wrapper.context.agent_stage = AgentStage.INCIDENT_FORMATTING

# Attach hooks to the nested agent
incident_formatter_agent.hooks = IncidentFormatterHooks()
```

### Pros
- **Lifecycle precision**: Hooks give you specific moments (`on_tool_start`, `on_tool_end`) that you can't access from inside a function_tool
- **Before/After actions**: Execute logic before the tool runs (validation, logging, stage updates) and after (capture results, trigger side effects)
- **Separation of concerns**: Agent definition is separate from state management
- **Reusable hooks**: Same hook class can be used across agents
- **Cleaner agent code**: Tools are defined simply with as_tool()
- **AI coding agent discoverability**: Hooks provide a "map" of the system's behavior, giving AI agents better context about what happens when

### Cons
- **Indirection**: State management happens in a different place than the tool
- **Requires understanding hooks**: Additional concept to learn

---

## Context Sharing: How It Works

Both approaches share context correctly when implemented properly.

### How as_tool() shares context

From the source code:
```python
# Inside as_tool()
run_result = await Runner.run(
    starting_agent=self,
    input=input,
    context=context.context,  # ToolContext.context is your TownHallContext
    # ...
)
```

The `ToolContext` (which extends `RunContextWrapper`) has a `.context` property containing your context object. This is automatically passed to the nested run.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Parent Runner.run()                      │
│                                                             │
│  ┌────────────────────────┐                                 │
│  │ Conversation Formatter │                                 │
│  │     Agent              │                                 │
│  │                        │                                 │
│  │  tools:                │                                 │
│  │  - incident_formatter  │──────┐                          │
│  │  - feedback_formatter  │      │                          │
│  │                        │      │                          │
│  │  hooks: on_tool_end()  │◄─────┼── captures result        │
│  └───────────────────────┘       │                          │
│              │                   │                          │
│              │ calls tool        │                          │
│              ▼                   │                          │
│  ┌───────────────────────┐       │                          │
│  │   Nested Runner.run() │       │                          │
│  │  (via as_tool or      │       │                          │
│  │   explicit call)      │       │                          │
│  │                       │       │                          │
│  │  context=ctx.context ─┼───────┼── same context object    │
│  │                       │       │                          │
│  │  returns final_output ─┼──────┘                          │
│  └───────────────────────┘                                  │
│              │                                              │
│              ▼                                              │
│  ┌───────────────────────┐                                  │
│  │    TownHallContext    │  ← Shared across all runs        │
│  │                       │                                  │
│  │  - incident           │                                  │
│  │  - feedback           │                                  │
│  │  - conversation       │                                  │
│  │  - agent_stage        │                                  │
│  └───────────────────────┘                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Lifecycle Precision: What Hooks Enable

One key advantage of Approach B is **lifecycle precision** - hooks give you specific moments that don't exist in Approach A.

### What You Can Do with Hooks

```python
class ConversationFormatterHooks(AgentHooks):
    async def on_tool_start(self, wrapper, agent, tool):
        """
        BEFORE the tool executes - not possible in Approach A
        
        Use cases:
        - Validate preconditions
        - Log the tool invocation
        - Update stage before processing
        - Check if we should proceed
        """
        print(f"🔧 Starting: {tool.name}")
        wrapper.context.current_tool = tool.name
        wrapper.context.agent_stage = AgentStage.PROCESSING
    
    async def on_tool_end(self, wrapper, agent, tool, result):
        """
        AFTER the tool completes - similar to what you'd do in Approach A,
        but separated from the tool logic itself
        
        Use cases:
        - Capture and store results
        - Trigger follow-up actions
        - Update processing flags
        - Log completion
        """
        if tool.name == "incident_formatter_tool":
            wrapper.context.incident = result
            wrapper.context.incident_processed = True
            print(f"✅ Incident captured")
```

### Comparison: Approach A vs B for Before/After

**Approach A** - Everything inside the function:
```python
@function_tool
async def incident_formatter_tool(ctx, conversation):
    # You CAN do "before" logic here...
    ctx.context.agent_stage = AgentStage.INCIDENT_FORMATTING
    
    result = await Runner.run(...)
    
    # ...and "after" logic here
    ctx.context.incident = result.final_output
    return result.final_output
```

**Approach B** - Lifecycle is external and discoverable:
```python
# Tool is simple
incident_formatter_tool = incident_formatter_agent.as_tool(...)

# Lifecycle is in hooks - visible and auditable
class Hooks(AgentHooks):
    async def on_tool_start(self, ...):   # Before
        ...
    async def on_tool_end(self, ...):     # After
        ...
```

The difference is subtle but important for larger systems where you want:
- A single place to see all lifecycle logic
- Easy auditing of what happens when
- AI coding agents to discover patterns

---

## Hook Types Reference

### AgentHooks

Lifecycle hooks for individual agents:

```python
from agents.lifecycle import AgentHooks
from agents import RunContextWrapper

class MyAgentHooks(AgentHooks):
    async def on_start(self, wrapper: RunContextWrapper[MyContext], agent):
        """Called when the agent starts running."""
        # Update instructions dynamically
        # Set stage
        pass
    
    async def on_end(self, wrapper: RunContextWrapper[MyContext], agent, run_item):
        """Called when the agent finishes."""
        # Capture final state
        # Transition to next stage
        pass
    
    async def on_tool_start(self, wrapper: RunContextWrapper[MyContext], agent, tool):
        """Called before a tool is executed."""
        pass
    
    async def on_tool_end(self, wrapper: RunContextWrapper[MyContext], agent, tool, result):
        """Called after a tool completes."""
        # Capture tool output and store in context
        if tool.name == "my_formatter":
            wrapper.context.formatted_data = result
        pass
```

### RunHooks

Lifecycle hooks for the entire run:

```python
from agents.lifecycle import RunHooks

class MyRunHooks(RunHooks):
    async def on_agent_start(self, wrapper: RunContextWrapper[MyContext], agent):
        """Called when any agent starts."""
        pass
    
    async def on_agent_end(self, wrapper: RunContextWrapper[MyContext], agent, output):
        """Called when any agent ends."""
        pass
    
    async def on_handoff(self, wrapper: RunContextWrapper[MyContext], from_agent, to_agent):
        """Called when a handoff occurs."""
        pass
```

### Handoff Callbacks

Update context when handoffs occur:

```python
from agents import handoff, RunContextWrapper

def _set_stage(stage: AgentStage):
    """Return an on_handoff callback that sets context.agent_stage."""
    def _callback(wrapper: RunContextWrapper[MyContext]):
        old_stage = wrapper.context.agent_stage
        wrapper.context.agent_stage = stage
        print(f"🔄 STAGE CHANGE: {old_stage.value} → {stage.value}")
    return _callback

# Use in handoff configuration
agent_a.handoffs = [
    handoff(
        agent_b,
        tool_name_override="transfer_to_agent_b",
        tool_description_override="Route to Agent B",
        on_handoff=_set_stage(AgentStage.AGENT_B_STARTED),
    )
]
```

---

## Practical Examples

### Example 1: Approach A - Explicit Nested Run

```python
# town_hall_agents/incident_formatter_agent.py
from agents import Agent, function_tool, RunContextWrapper, Runner
from core.models import Incident
from core.context import TownHallContext, AgentStage

incident_formatter_agent = Agent(
    name="Incident Formatter Agent",
    instructions="You are an incident agent. Your job is to convert the conversation into a reporting incident.",
    output_type=Incident
)

@function_tool
async def incident_formatter_tool(
    ctx: RunContextWrapper[TownHallContext],
    conversation: str
) -> Incident:
    """
    Format an incident from the conversation.
    Use this tool for formatting incidents (i.e. lost items, anomalies, violations, crime)
    """
    ctx.context.agent_stage = AgentStage.INCIDENT_FORMATTING
    
    result = await Runner.run(
        starting_agent=incident_formatter_agent,
        input=conversation,
        context=ctx.context
    )
    
    incident = result.final_output
    ctx.context.incident = incident
    ctx.context.incident_processed = True
    
    return incident
```

### Example 2: Approach B - as_tool() with Parent Hooks

```python
# town_hall_agents/incident_formatter_agent.py
from agents import Agent
from core.models import Incident

incident_formatter_agent = Agent(
    name="Incident Formatter Agent",
    instructions="You are an incident agent. Your job is to convert the conversation into a reporting incident.",
    output_type=Incident
)

incident_formatter_tool = incident_formatter_agent.as_tool(
    tool_name="incident_formatter_tool",
    tool_description="Use this tool for formatting incidents (i.e. lost items, anomalies, violations, crime)"
)
```

```python
# town_hall_agents/hooks.py
from agents.lifecycle import AgentHooks
from agents import RunContextWrapper
from core.context import TownHallContext, AgentStage
from typing import Any

class ConversationFormatterHooks(AgentHooks):
    async def on_tool_end(self, wrapper: RunContextWrapper[TownHallContext], agent, tool, result: Any):
        if tool.name == "incident_formatter_tool":
            wrapper.context.incident = result
            wrapper.context.incident_processed = True
            wrapper.context.agent_stage = AgentStage.INCIDENT_FORMATTING
            print(f"✅ Incident stored in context")
        
        elif tool.name == "feedback_formatter_tool":
            wrapper.context.feedback = result
            wrapper.context.feedback_processed = True
            wrapper.context.agent_stage = AgentStage.FEEDBACK_FORMATTING
            print(f"✅ Feedback stored in context")
```

```python
# town_hall_agents/__init__.py (attach hooks)
from town_hall_agents.conversation_formatter_agent import conversation_formatter_agent
from town_hall_agents.hooks import ConversationFormatterHooks

conversation_formatter_agent.hooks = ConversationFormatterHooks()
```

### Example 3: Dynamic Instructions Based on Stage

```python
class TriageAgentHooks(AgentHooks):
    async def on_start(self, wrapper: RunContextWrapper[TownHallContext], agent):
        """Format instructions with current stage."""
        current_stage = wrapper.context.agent_stage.value
        
        # Dynamically update instructions
        agent.instructions = TRIAGE_INSTRUCTIONS.format(
            agent_stage=current_stage
        )
        print(f"📋 Triage Agent instructions updated for stage: {current_stage}")
```

### Example 4: Stage Transitions on Handoff

```python
def _to_incident_formatting(wrapper: RunContextWrapper[TownHallContext]):
    wrapper.context.agent_stage = AgentStage.INCIDENT_FORMATTING
    print("🔄 Stage → INCIDENT_FORMATTING")

def _to_feedback_formatting(wrapper: RunContextWrapper[TownHallContext]):
    wrapper.context.agent_stage = AgentStage.FEEDBACK_FORMATTING
    print("🔄 Stage → FEEDBACK_FORMATTING")

conversation_formatter_agent.handoffs = [
    handoff(
        incident_formatter_agent,
        tool_name_override="format_incident",
        on_handoff=_to_incident_formatting,
    ),
    handoff(
        feedback_formatter_agent,
        tool_name_override="format_feedback",
        on_handoff=_to_feedback_formatting,
    ),
]
```

---

## When to Use What

| Scenario | Approach A (Explicit) | Approach B (as_tool + Hooks) |
|----------|----------------------|------------------------------|
| Simple, self-contained tools | ✅ Preferred | Works |
| Need before/after lifecycle actions | Limited (only inside function) | ✅ `on_tool_start`/`on_tool_end` |
| Cross-tool state dependencies | Manual tracking | ✅ Centralized in hooks |
| AI coding agent will extend the code | Harder to discover patterns | ✅ Hooks provide system "map" |
| Teaching/learning | ✅ More explicit | Requires hook knowledge |
| Debugging | ✅ Everything in one place | State logic in hooks |

### Decision Guide

```
Do you need lifecycle precision (before/after tool execution)?
├── Yes: Use Approach B (hooks)
│   - on_tool_start: validation, logging, stage updates before execution
│   - on_tool_end: capture results, trigger side effects after execution
│
└── No: Consider your other needs
    │
    ├── Simple tool with 1-2 context updates?
    │   └── Use Approach A (explicit) - self-contained, easy to read
    │
    ├── AI coding agent will extend this codebase?
    │   └── Use Approach B (hooks) - provides discoverable patterns
    │
    └── Cross-tool state dependencies?
        └── Use Approach B (hooks) - centralized state management
```

### Why Hooks Help AI Coding Agents

When hooks are defined in your codebase, they serve as a "map" of system behavior:

```python
# An AI agent can scan this and understand:
# - What happens when tools are called
# - What state gets updated and when
# - The lifecycle of each agent
class ConversationFormatterHooks(AgentHooks):
    async def on_tool_start(self, wrapper, agent, tool):
        # AI sees: "before any tool, we log and set stage"
        print(f"🔧 Tool starting: {tool.name}")
        wrapper.context.current_tool = tool.name
    
    async def on_tool_end(self, wrapper, agent, tool, result):
        # AI sees: "after incident_formatter_tool, we store the result"
        if tool.name == "incident_formatter_tool":
            wrapper.context.incident = result
            wrapper.context.incident_processed = True
```

This discoverability helps AI agents:
1. Understand the existing patterns
2. Follow consistent conventions when adding new features
3. Know where to add new lifecycle logic

### Both Are Valid

The OpenAI community feedback confirms both approaches are acceptable. Choose based on:

1. **Lifecycle needs**: Do you need before/after hooks? Use Approach B
2. **Team preference**: Which style does your team prefer?
3. **AI-assisted development**: Hooks provide better context for AI agents
4. **Teaching context**: Explicit code is often easier for students to understand initially

---

## Summary

1. **Both approaches create nested runs** - `as_tool()` is syntactic sugar that calls `Runner.run()` internally.

2. **Context is shared in both** - as long as you pass `ctx.context` (Approach A) or use `as_tool()` which does this automatically.

3. **Approach A (explicit)** - Full control, self-contained, everything in one place. Best for simple tools or when teaching.

4. **Approach B (hooks)** - Lifecycle precision with `on_tool_start`/`on_tool_end`, separation of concerns, discoverable patterns for AI coding agents.

5. **Choose Approach B when**:
   - You need before/after lifecycle actions
   - You want AI coding agents to understand your system's behavior
   - You have cross-tool state dependencies
   - You want a centralized "map" of what happens when

6. **Choose Approach A when**:
   - Simple, self-contained tools
   - Teaching beginners (explicit code is clearer)
   - You prefer everything in one place for debugging

## Related Files

- [`docs/agent-as-tool.md`](./agent-as-tool.md) - Deep dive into how `as_tool()` works internally
- [`town_hall_agents/__init__.py`](../town_hall_agents/__init__.py) - Where hooks can be attached
- [`core/context.py`](../core/context.py) - The shared context class
- [`docs/circular-imports.md`](./circular-imports.md) - Related import patterns
