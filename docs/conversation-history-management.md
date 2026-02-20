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
- 2.1`SQLiteSession` - SQLite database (in-memory or file)
- 2.2 `OpenAIConversationSession` - Stores conversation history on OpenAI Servers
- 2.3 `SQLAlchemySession` - Any SQLAlchemy-supported database (PostgreSQL, MySQL, etc.) See [SQLAlchemySession](./sqlalchemy-guide.md)
- 2.4 `EncryptedSession` - Encrypted wrapper with optional TTL

**Expiration**: Depends on configuration:
- In-memory SQLite: Lost when process ends
- File-based SQLite: Persists until deleted
- EncryptedSession with TTL: Expires after specified duration
- Hosted database (Supabase / AWS / Google Cloud): Persists indefinitely. Supabase free tier projects may pause after ~7 days of inactivity and wake on the next request. Cloud providers (AWS/GCP) typically do not expire but may incur charges if a paid instance is provisioned. 

#### 2.1 with 2.4 `SQLiteSession` with `EncryptedSession`
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
- Works immediately with minimal code
- Fast local reads/writes
- Works offline
- Ideal for development, testing, and single-machine deployments
- File-based mode gives simple persistence
- Easy to reset by deleting the database file
- Optional TTL and encryption available

**Cons**:
- Not suitable for multiple servers or containers
- Sessions tied to one machine (no horizontal scaling)
- Not ideal for production web backends

---

#### 2.2 Using OpenAIConversationSession (OpenAI-Hosted)

**How it works**: OpenAI stores the conversation history on their servers.

**Storage**: OpenAI's servers.

**Expiration**: Managed by OpenAI (see their documentation for retention policies).

```python
from agents import Agent, Runner
from agents import OpenAIConversationSession

async def main():
    
    session = OpenAIConversationsSession()
    agent = Agent(name="Assistant")
    
    with trace(workflow_name):
        while True:
            try:
                user_input = input(">") #Terminal Input example
                continue
        
        result = Runner.run_streamed(
            agent,
            user_input,
            session=session)
    
        # Then Stream response if wanted
```
**Pros**:
- No database to manage
- Works immediately in serverless environments
- Accessible across multiple instances automatically
- Simplest deployment option
- Good for prototypes and demos
- Optional TTL and encryption available

**Cons**:
- Dependent on network and OpenAI availability

#### 2.3 SQLAlchemySession (PostgreSQL/MySQL/etc.)
See [SQLAlchemySession](./sqlalchemy-guide.) for the detailed instructions and explanations.

**Pros**:
- Production-grade persistence
- Supports multiple servers and containers
- Works with managed databases (PostgreSQL, MySQL, etc.)
- Centralized storage for all users
- Better durability and reliability
- Can be backed up and inspected
- Optional TTL and encryption available

**Cons**: 
- Requires database provisioning and maintenance
- More setup complexity
- Possible hosting costs
- Requires connection pooling and configuration in larger deployments
- Overkill for small or single-user applications


## Storage and Expiration Summary

| Approach | Storage Location | Default Expiration 
|----------|-----------------|-------------------|
| Manual (`to_input_list()`) | Your app's memory | When variables go out of scope |
| `SQLiteSession` (in-memory) | RAM | When process ends |
| `SQLiteSession` (file) | Local SQLite file | Never (until deleted) |
| `SQLAlchemySession` | Your database | Never (until deleted) |
| `EncryptedSession` | Underlying session | Configurable TTL |
| `OpenAIConversationsSession` | OpenAI servers | OpenAI's retention policy |

---

## Best Practices

### For Development/Testing
```python
# Use in-memory SQLite - fast, no cleanup needed
session = SQLiteSession("test_session")
```

### For Production Chat Applications
```python
# PostgreSQL/MySQL
from agents.extensions.memory import SQLAlchemySession
session = SQLAlchemySession.from_url(
    "user_123",
    url="postgresql+asyncpg://user:pass@localhost/db",
    create_tables=True
)

# Or for Serverless/Stateless Deployments
from agents import Agent, Runner, OpenAIConversationsSession
session = OpenAIConversationsSession()
result = await Runner.run(
    agent,
    "What city is the Golden Gate Bridge in?",
    session=session
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
---

## References

### Official Documentation
- [OpenAI Agents SDK - Sessions](https://openai.github.io/openai-agents-python/sessions/)
- [OpenAI Agents SDK - SQLAlchemy](https://openai.github.io/openai-agents-python/sessions/sqlalchemy_session/)
- [OpenAI Agents SDK - Main ClassSQLAlchemy](https://openai.github.io/openai-agents-python/ref/extensions/memory/sqlalchemy_session/#agents.extensions.memory.sqlalchemy_session.SQLAlchemySession)
- [SQLAlchemy - 2026](https://www.youtube.com/watch?v=Y-TxICRUy_k)
- [OpenAI Conversation State Guide](https://platform.openai.com/docs/guides/conversation-state?api-mode=responses)
- [OpenAI Agents SDK - Running Agents](https://openai.github.io/openai-agents-python/running_agents/)
### Source Code
- [run.py](https://github.com/openai/openai-agents-python/blob/main/src/agents/run.py) - Runner implementation
- [result.py](https://github.com/openai/openai-agents-python/blob/main/src/agents/result.py) - RunResult and `to_input_list()`
- [memory/](https://github.com/openai/openai-agents-python/tree/main/src/agents/memory) - Session implementations
