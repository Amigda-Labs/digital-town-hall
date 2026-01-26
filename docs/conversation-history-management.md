# Conversation History Management in OpenAI Agents SDK

This document explains how conversation history (the `input` list) is stored, managed, and persisted in the OpenAI Agents SDK.

## Table of Contents

- [Overview](#overview)
- [How Input is Stored](#how-input-is-stored)
- [The `to_input_list()` Method](#the-to_input_list-method)
- [Three Ways to Manage Conversation History](#three-ways-to-manage-conversation-history)
- [Storage and Expiration](#storage-and-expiration)
- [References](#references)

---

## Overview

When you run an agent, the SDK needs to maintain conversation history so that:
1. The LLM can see previous messages and maintain context
2. Tools can receive relevant information to extract parameters
3. Multi-turn conversations work properly

The key question is: **Where is this history stored and for how long?**

The answer: **It depends on which approach you choose.**

---

## How Input is Stored

During a single `Runner.run()` call, the conversation history is stored in **local Python variables** within the Runner:

```python
# Inside Runner.run() - simplified
original_input: str | list[TResponseInputItem] = input
generated_items: list[RunItem] = []  # Items generated during this run

while True:
    # Each turn accumulates items
    input = ItemHelpers.input_to_new_input_list(original_input)
    input.extend([item.to_input_item() for item in generated_items])
    
    # Send to LLM
    response = await model.get_response(..., input=input, ...)
    
    # Process response, add to generated_items
    generated_items.extend(new_items)
```

**Key insight**: Within a single `Runner.run()` call, the history lives in memory. Once the call completes and returns a `RunResult`, that memory is released.

---

## The `to_input_list()` Method

The `RunResult` object has a method called `to_input_list()` that converts the run's history into a format suitable for the next turn:

```python
# From RunResult
def to_input_list(self) -> list[TResponseInputItem]:
    """
    Convert the result to an input list for the next turn.
    Returns the original input + all new items generated during the run.
    """
    original = ItemHelpers.input_to_new_input_list(self.input)
    return original + [item.to_input_item() for item in self.new_items]
```

### What it Returns

`to_input_list()` returns a list of input items in the format expected by the OpenAI Responses API:

```python
[
    {"role": "user", "content": "What city is the Golden Gate Bridge in?"},
    {"role": "assistant", "content": "San Francisco"},
    {"role": "user", "content": "What state is it in?"},
    # ... etc
]
```

### Usage Example

```python
# First turn
result = await Runner.run(agent, "What city is the Golden Gate Bridge in?")
print(result.final_output)  # "San Francisco"

# Second turn - manually pass the history
new_input = result.to_input_list() + [{"role": "user", "content": "What state is it in?"}]
result = await Runner.run(agent, new_input)
print(result.final_output)  # "California"
```

---

## Three Ways to Manage Conversation History

The SDK provides three approaches, each with different storage and expiration characteristics:

### 1. Manual Management with `to_input_list()`

**How it works**: You manually pass conversation history between runs.

**Storage**: In your application's memory (Python variables).

**Expiration**: When your application closes or variables go out of scope.

```python
async def main():
    agent = Agent(name="Assistant")
    
    # First turn
    result = await Runner.run(agent, "Hello!")
    
    # Second turn - YOU manage the history
    new_input = result.to_input_list() + [{"role": "user", "content": "How are you?"}]
    result = await Runner.run(agent, new_input)
```

**Pros**:
- Full control over what's stored
- No external dependencies

**Cons**:
- You must manually track history
- Lost when app restarts (unless you serialize it)

---

### 2. Sessions (Automatic Local/Database Storage)

**How it works**: The SDK automatically stores and retrieves conversation history using a Session object.

**Storage**: Depends on session type:
- `SQLiteSession` - SQLite database (in-memory or file)
- `SQLAlchemySession` - Any SQLAlchemy-supported database (PostgreSQL, MySQL, etc.)
- `EncryptedSession` - Encrypted wrapper with optional TTL

**Expiration**: Depends on configuration:
- In-memory SQLite: Lost when process ends
- File-based SQLite: Persists until deleted
- EncryptedSession with TTL: Expires after specified duration

```python
from agents import Agent, Runner, SQLiteSession

# In-memory (temporary) - EXPIRES when process ends
session = SQLiteSession("conversation_123")

# File-based (persistent) - NO EXPIRATION
session = SQLiteSession("conversation_123", "conversations.db")

# With TTL (expiration) - EXPIRES after 600 seconds
from agents.extensions.memory import EncryptedSession
session = EncryptedSession(
    session_id="user_123",
    underlying_session=SQLiteSession("user_123", "db.sqlite"),
    encryption_key="your-secret-key",
    ttl=600  # 10 minutes
)

# Use in runner - history is automatic
result = await Runner.run(agent, "Hello", session=session)
result = await Runner.run(agent, "How are you?", session=session)  # Remembers!
```

**Pros**:
- Automatic history management
- Persistent storage options
- Can set TTL for expiration
- Production-ready options

**Cons**:
- Requires choosing and configuring a session type
- May need database setup

---

### 3. Server-Managed Conversations (OpenAI-Hosted)

**How it works**: OpenAI stores the conversation history on their servers.

**Storage**: OpenAI's servers.

**Expiration**: Managed by OpenAI (see their documentation for retention policies).

```python
from agents import Agent, Runner
from openai import AsyncOpenAI

client = AsyncOpenAI()

async def main():
    agent = Agent(name="Assistant")
    
    # Create a server-managed conversation
    conversation = await client.conversations.create()
    conv_id = conversation.id
    
    # First turn - OpenAI stores the history
    result = await Runner.run(agent, "Hello", conversation_id=conv_id)
    
    # Second turn - OpenAI provides the history
    result = await Runner.run(agent, "How are you?", conversation_id=conv_id)
```

**Pros**:
- No local storage needed
- Handles large conversations
- Built-in compaction

**Cons**:
- Requires OpenAI API
- Data stored on OpenAI servers
- Subject to OpenAI's retention policies

---

## Storage and Expiration Summary

| Approach | Storage Location | Default Expiration | Can Set TTL? |
|----------|-----------------|-------------------|--------------|
| Manual (`to_input_list()`) | Your app's memory | When variables go out of scope | N/A (you control it) |
| `SQLiteSession` (in-memory) | RAM | When process ends | No |
| `SQLiteSession` (file) | Local SQLite file | Never (until deleted) | No |
| `SQLAlchemySession` | Your database | Never (until deleted) | No |
| `EncryptedSession` | Underlying session | Configurable TTL | Yes |
| `OpenAIConversationsSession` | OpenAI servers | OpenAI's retention policy | No |
| Server-managed (`conversation_id`) | OpenAI servers | OpenAI's retention policy | No |

---

## Best Practices

### For Development/Testing
```python
# Use in-memory SQLite - fast, no cleanup needed
session = SQLiteSession("test_session")
```

### For Production Chat Applications
```python
# Use file-based SQLite or database-backed session
session = SQLiteSession("user_123", "conversations.db")

# Or for PostgreSQL/MySQL
from agents.extensions.memory import SQLAlchemySession
session = SQLAlchemySession.from_url(
    "user_123",
    url="postgresql+asyncpg://user:pass@localhost/db",
    create_tables=True
)
```

### For Sensitive Data with Expiration
```python
from agents.extensions.memory import EncryptedSession

session = EncryptedSession(
    session_id="user_123",
    underlying_session=SQLiteSession("user_123", "secure.db"),
    encryption_key="your-encryption-key",
    ttl=3600  # 1 hour expiration
)
```

### For Serverless/Stateless Deployments
```python
# Use OpenAI-hosted conversations
result = await Runner.run(
    agent, 
    user_input, 
    conversation_id=conv_id  # OpenAI manages storage
)
```

---

## How This Relates to Function Tools

When a tool like `feedback_formatter_tool` is called:

1. The `conversation_format_coordinator_agent` has accumulated conversation history through handoffs
2. This history is stored in the `input` list (as described above)
3. The LLM sees this history and can extract information from it
4. When the LLM calls your tool, it provides the `conversation` parameter based on what it saw

```
User talks to dialogue_agent
         │
         ▼
    [input list grows]
         │
         ▼
dialogue_agent hands off to triage_agent
         │
         ▼
    [input list carries over]
         │
         ▼
triage_agent hands off to conversation_format_coordinator_agent
         │
         ▼
    [input list still has full history]
         │
         ▼
LLM decides to call feedback_formatter_tool(conversation="...")
         │
         ▼
    [LLM extracts 'conversation' from what it saw in the input list]
```

The LLM has access to the full conversation history through the `input` list. It uses this to provide the `conversation` parameter to your tool.

---

## References

### Official Documentation
- [OpenAI Agents SDK - Running Agents](https://openai.github.io/openai-agents-python/running_agents/)
- [OpenAI Agents SDK - Sessions](https://openai.github.io/openai-agents-python/sessions/)
- [OpenAI Conversation State Guide](https://platform.openai.com/docs/guides/conversation-state?api-mode=responses)

### Source Code
- [run.py](https://github.com/openai/openai-agents-python/blob/main/src/agents/run.py) - Runner implementation
- [result.py](https://github.com/openai/openai-agents-python/blob/main/src/agents/result.py) - RunResult and `to_input_list()`
- [memory/](https://github.com/openai/openai-agents-python/tree/main/src/agents/memory) - Session implementations

### Related Documentation in This Project
- [`docs/function-tool-deep-dive.md`](./function-tool-deep-dive.md) - How `@function_tool` works with context
- [`docs/hooks-vs-nested-runs.md`](./hooks-vs-nested-runs.md) - Managing state in nested agent runs
