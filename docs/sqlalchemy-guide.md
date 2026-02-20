# SQLAlchemy Guide for Beginners 

This guide explains how session management for **production** works in the Digital Town Hall project. This guide will be using SQLAlchemySession to help manage the session. This covers database connections, ORM models, and session persistence.

## Table of Contents
- [Database Storage Architecture](#database-storage-architecture)
- [General Concept](#general-concept)
- [SQLAlchemy vs Database Drivers](#sqlalchemy-vs-database-drivers)
- [What are ORM Models?](#what-are-orm-models)
- [Connection Strings Explained](#connection-strings-explained)
- [Setting Up with Supabase](#setting-up-with-supabase)
- [How Sessions Work](#how-sessions-work)
- [Project Structure](#project-structure)

---
## Database Storage Architecture
We are using two different implementations that will upload data to our database. Both relate to SQLAlchemy, but they serve different purposes. 

1. **Agents SDK SQLAlchemySession (Conversation Memory)**
- We use the SQLAlchemySession provided by the OpenAI Agents SDK to automatically store agent conversations — including session state and message history. The SDK manages this internally and requires no manual schema handling from us.
```python
from agents.extensions.memory import SQLAlchemySession
```

2. **SQLAlchemy ORM (Application Data Storage)** 
- We use the official SQLAlchemy ORM library to define our own database models and store structured output data (e.g., incidents and feedback). Here, we fully control the schema, tables, and how records are saved.  
```python
from sqlalchemy import String, Integer, Float, Boolean, Date, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
```


## General Concept 
For data to be stored in the database, it must be **committed** through a SQLAlchemy session.  
SQLAlchemy does not write directly to the database when you create an object — it only prepares it.  
The actual database write happens during the commit step.

The typical flow is:

1. Provide the database URL  
2. Create a SQLAlchemy engine  
3. Create a session using the engine  
4. Add objects to the session  
5. Commit the session to persist the data

If you use the SQLAlchemy Extension by openai, you would just have to provide the database url and it will automatically upload the `agent_sessions` and `agent_messages` by default. The extension automatically commits the session to your database for every run.

```python
from agents.extensions.memory import SQLAlchemySession

# Create session using database URL
    session = SQLAlchemySession.from_url(
        "user-123",
        url="sqlite+aiosqlite:///:memory:",
        create_tables=True
    )
# Refer to `src/agents/extensions/memory/sqlalchemy_session.py` from the SDK extension if you want to specifically change names or configure table settings
```

If you are storing structured output in a database, it is ideal to validate 
your data using Pydantic BaseModels, then map and persist it through 
SQLAlchemy ORM models (which inherit from DeclarativeBase).

In the Town Hall project, we want to store the structured outputs of specific agents. 
These structured outputs are returned by `@function_tool` decorated functions — 
specifically `feedback_formatter_tool` and its Incident counterpart. Each tool runs 
a nested agent (e.g., `feedback_formatter_agent`) whose `final_output` is a validated 
Pydantic model (e.g., `Feedback`), which is then persisted to the database via a 
`save_feedback()` call before being returned.

**High level flow**
→ `@function_tool` → runs nested agent → returns Pydantic model (`Feedback` / `Incident`)
→ passed to `save_feedback()` / `save_incident()` (From the database.py that contains the SQLAlchemy engine)
→ fields mapped to `FeedbackModel` / `IncidentModel`
→ added to `AsyncSession` → committed to database → refreshed with generated `id`


**Why have Pydantic models and ORM models separately?**
This enforces a clear separation of concerns:

- **Pydantic models** — define the agent's structured output (validation, typing, AI-facing shape)
- **ORM models** — define the database table structure (persistence, DB-facing shape)

Keeping them separate means changes to one don't break the other.

**Why use not use only OpenAI SQLAlchemy Extension alone? why still use the Original SQLAlchemy**
Merging them would be problematic because the SDK's session is not designed to store your custom structured outputs, and forcing your ORM models into it would couple your application data to the SDK's internal memory mechanism — making it fragile if the SDK changes. Keeping them separate means your conversation memory and your application data are independently managed, with no risk of one breaking the other.

**The Problem Without SQLAlchemy**
To save data to a database, you'd normally have to write raw SQL — a separate 
query language with its own syntax, separate from your Python code:
```sql
INSERT INTO incidents (incident_type, description, location) 
VALUES ('pothole', 'Big hole on Main St', 'Tokyo');
```
This means switching between two languages, and any typo or mismatch between 
your Python data and your SQL query can cause errors.

**The Solution With SQLAlchemy**
SQLAlchemy lets you save data using plain Python objects instead — no SQL required:
```python
incident = IncidentModel(
    incident_type="pothole",
    description="Big hole on Main St",
    location="Tokyo"
)
session.add(incident)
await session.commit()
```
SQLAlchemy translates your Python objects into the equivalent SQL queries automatically, 
keeping everything in one language and reducing the chance of errors.

## SQLAlchemy vs Database Drivers

Think of it as a two-layer system:
```
Your Python Code
       ↓
SQLAlchemy (translates Python objects → SQL queries)
       ↓
Database Driver (knows how to "talk" to a specific database)
       ↓
Database (PostgreSQL, SQLite, MySQL, etc.)
```

**SQLAlchemy** only handles the translation — it converts your Python objects 
into SQL queries, but it doesn't know how to deliver them to a specific database.

**The Database Driver** is the adapter that handles the actual communication. 
Each database has its own protocol (its own "language" for receiving connections 
and queries), so you need a driver that speaks that specific protocol.

For example:
- `aiosqlite` — driver for SQLite
- `asyncpg` — driver for PostgreSQL
- `aiomysql` — driver for MySQL

This is why in `database.py` the connection URL is:
```python
"sqlite+aiosqlite:///town_hall.db"
 ↑               ↑
 database        driver
```
SQLAlchemy uses the URL to know which driver to hand off to once the SQL is ready.

### Why Both Are Needed

| Component | What It Does | Example |
|-----------|--------------|---------|
| **SQLAlchemy** | Generates SQL from Python objects | `session.add(incident)` → `INSERT INTO...` |
| **Database Driver** | Actually connects and sends queries to the database | `asyncpg`, `aiosqlite` |

### Different Databases Need Different Drivers

| Database | Async Driver | Install Command |
|----------|--------------|-----------------|
| SQLite | `aiosqlite` | `pip install aiosqlite` |
| PostgreSQL | `asyncpg` | `pip install asyncpg` |
| MySQL | `aiomysql` | `pip install aiomysql` |

*SQLAlchemy is the translator, the driver is the messenger.*

---

## What are ORM Models?

**ORM** = Object-Relational Mapping

It maps Python classes to database tables.

### Pydantic Models vs ORM Models

This project uses **both** types of models:

#### Pydantic Models (`core/models.py`)
- Used for **data validation** and **type checking**
- Data exists **only in memory**
- Used by agents to structure their outputs

```python
# Pydantic model - validates data, doesn't save to database
class Incident(BaseModel):
    incident_type: str
    description: str
    location: str
```

#### SQLAlchemy ORM Models (`core/database.py`)
- Used for **database storage**
- Data **persists** in the database
- Maps directly to database tables

```python
# SQLAlchemy model - saves to database
class IncidentModel(Base):
    __tablename__ = "incidents"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_type: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(255))
```

### The Flow

```
Agent extracts data
       ↓
Pydantic model (validates structure)
       ↓
SQLAlchemy model (saves to database)
       ↓
Data persists in PostgreSQL/SQLite
```

---

## Connection Strings Explained

Connection strings tell SQLAlchemy **how** and **where** to connect.

### Format

```
driver+async_driver://username:password@host:port/database_name
```

### Breaking It Down

```
postgresql+asyncpg://postgres:mypassword@db.xxx.supabase.co:5432/postgres
│          │         │       │          │                   │    │
│          │         │       │          │                   │    └── Database name
│          │         │       │          │                   └── Port number
│          │         │       │          └── Host (server address)
│          │         │       └── Password
│          │         └── Username
│          └── Async driver (asyncpg for PostgreSQL)
└── Database type (postgresql)
```

### Common Examples

| Database | Connection String |
|----------|-------------------|
| **SQLite (local file)** | `sqlite+aiosqlite:///town_hall.db` |
| **Supabase (pooler)** | `postgresql+asyncpg://postgres.xxx:PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres` |
| **Local PostgreSQL** | `postgresql+asyncpg://user:pass@localhost:5432/mydb` |

### The `+asyncpg` Part

This tells SQLAlchemy to use the **async** driver. Without it:
- `postgresql://` → synchronous (blocks your code)
- `postgresql+asyncpg://` → asynchronous (non-blocking)

For this project, we use async because the OpenAI Agents SDK is async.

---

## Connection Pooling vs Direct Connection

When connecting to Supabase, you have two options. Understanding when to use each is important for production applications.

### What is Connection Pooling?

**Direct Connection:** Each user = 1 database connection. PostgreSQL has limits (~100-500 connections max).

**Connection Pooling (pgbouncer):** Many users share a smaller pool of database connections. 1000 users might share just 20 actual connections.

```
Without Pooling:                    With Pooling:
User 1 ──→ Connection 1             User 1 ──┐
User 2 ──→ Connection 2             User 2 ──┼──→ Pool ──→ 20 Connections
User 3 ──→ Connection 3             User 3 ──┤           to Database
...                                 ...      │
User 1000 ──→ Connection 1000       User 1000┘
(Database overwhelmed!)             (Database happy!)
```

### Supabase Connection Options

Supabase provides two connection strings in **Connect** → **ORMs**:

| Type | Port | Use Case |
|------|------|----------|
| **Connection Pooling** | `6543` | Production apps, many simultaneous users |
| **Direct Connection** | `5432` | Database migrations, admin tasks, development |

For migrations and schema changes you want the direct connection, because PgBouncer in transaction mode can swap your connection to a different backend mid-migration — and when that happens, that new connection has no memory of what the previous session set up, like prepared statements, advisory locks, or session settings, which can cause your migration tool to fail or behave unpredictably.

### Which Should You Use?

| Scenario | Recommendation |
|----------|----------------|
| Learning/Development | Either works |
| Production with few users (<50) | Either works |
| Production with many users (100+) | **Use Connection Pooling (port 6543)** |
| Running database migrations | Use Direct Connection (port 5432) |
| Schema changes (CREATE TABLE, etc.) | Use Direct Connection (port 5432) |

### Important: Remove `?pgbouncer=true`

Supabase's ORM connection string includes `?pgbouncer=true`:

```bash
# What Supabase gives you (won't work with asyncpg!)
postgresql://postgres.xxx:PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres?pgbouncer=true

# What you should use (remove the parameter, add +asyncpg)
postgresql+asyncpg://postgres.xxx:PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres
```

The `?pgbouncer=true` parameter is not supported by `asyncpg`. Just remove it - the pooler works without it.

---

## Setting Up with Supabase

### Step 1: Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign in
2. Click **"New Project"**
3. Name your project and set a **database password** (save it!)
4. Choose a region close to you
5. Wait ~2 minutes for setup

### Step 2: Get Your Connection String

1. In Supabase project dashboard: Click **Connect** → **ORMs**
2. You'll see two connection strings:
   ```bash
   # Connection pooling (for your app - use this one)
   DATABASE_URL="postgresql://postgres.xxx:[YOUR-PASSWORD]@aws-0-region.pooler.supabase.com:6543/postgres?pgbouncer=true"
   
   # Direct connection (for migrations only)
   DIRECT_URL="postgresql://postgres.xxx:[YOUR-PASSWORD]@aws-0-region.pooler.supabase.com:5432/postgres"
   ```
3. Copy the **first one** (connection pooling, port 6543)
4. Replace `[YOUR-PASSWORD]` with your actual database password

### Step 3: Update for Async

Make two changes to the connection string:
1. Add `+asyncpg` after `postgresql`
2. Remove `?pgbouncer=true` at the end

```bash
# Before (from Supabase - won't work)
postgresql://postgres.xxx:password@aws-0-region.pooler.supabase.com:6543/postgres?pgbouncer=true

# After (works with asyncpg)
postgresql+asyncpg://postgres.xxx:password@aws-0-region.pooler.supabase.com:6543/postgres
```

### Step 4: Add to `.env`

```bash
# Production - uses connection pooling (port 6543) for scalability
DATABASE_URL="postgresql+asyncpg://postgres.xxx:YOUR_PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres"
```

### Step 5: Install Dependencies

**Option 1: Using `uv add` (Recommended)**

```bash
uv add asyncpg greenlet
```

This automatically adds the dependencies to `pyproject.toml` and installs them.

**Option 2: Manual Edit**

Add these to your `pyproject.toml`:
```toml
dependencies = [
    "openai-agents[sqlalchemy]>=0.6.5",
    "asyncpg>=0.30.0",      # PostgreSQL async driver
    "greenlet>=3.0.0",      # Required for SQLAlchemy async operations
]
```

Then run:
```bash
uv sync
```

### Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `No module named 'greenlet'` | Missing dependency | Run `uv add greenlet` |
| `unexpected keyword argument 'pgbouncer'` | `?pgbouncer=true` in URL | Remove `?pgbouncer=true` from DATABASE_URL |
| `nodename nor servname provided` | Can't reach database | Check if Supabase project is paused, or hostname is correct |
| `could not parse statement` | Malformed `.env` | Check for missing quotes in `.env` file |
| `connection refused` | Wrong port or database offline | Verify port (6543 for pooler, 5432 for direct) |

---

## How Sessions Work

### SQLAlchemySession for Conversations

The OpenAI Agents SDK uses `SQLAlchemySession` to persist conversation history.

```python
from agents.extensions.memory import SQLAlchemySession

session = SQLAlchemySession.from_url(
    "user-123",           # Session identifier
    url=DATABASE_URL,
    create_tables=True,   # Auto-create tables on first run
)
```

### How It Persists Memory

```
User: "Hi, I'm Jao"
       ↓
Agent responds
       ↓
SQLAlchemySession saves to database:
  - user message: "Hi, I'm Jao"
  - agent response: "Hello Jao!"
       ↓
[App restarts]
       ↓
User: "What's my name?"
       ↓
SQLAlchemySession loads history from database
       ↓
Agent sees previous messages
       ↓
Agent: "Your name is Jao!"
```

### Session Identifiers

The first parameter is the **session ID**. Same ID = same conversation history.

```python
# All conversations share history (current setup)
session = SQLAlchemySession.from_url("town-hall-user", ...)

# Each user gets their own history
session = SQLAlchemySession.from_url(f"user-{user_id}", ...)

# Each conversation is separate
session = SQLAlchemySession.from_url(f"conv-{uuid.uuid4()}", ...)
```

---

## Project Structure

### Database-Related Files

```
digital-town-hall/
├── core/
│   ├── database.py          # SQLAlchemy models & DB utilities
│   ├── models.py            # Pydantic models (validation only)
│   └── main.py              # App entry, initializes DB
├── town_hall_agents/
│   ├── incident_formatter_agent.py   # Saves incidents to DB
│   └── feedback_formatter_agent.py   # Saves feedback to DB
├── .env                      # DATABASE_URL goes here
└── pyproject.toml            # Dependencies
```

### How Data Flows

```
1. User reports incident
       ↓
2. dialogue_agent collects details
       ↓
3. User says "that's all"
       ↓
4. Handoff to triage_agent → conversation_format_coordinator_agent
       ↓
5. incident_formatter_tool runs:
   a. Creates Pydantic Incident (validation)
   b. Calls save_incident() → SQLAlchemy model → Database
       ↓
6. Data persists in Supabase
```

### Viewing Your Data

After running conversations, check Supabase:

1. Go to **Table Editor** in Supabase dashboard
2. You'll see tables:
   - `incidents` - Reported incidents
   - `feedback` - User feedback
   - Session tables - Conversation history

---

## Quick Reference

### Environment Variables

```bash
# .env file - Use connection pooling (port 6543) for production
DATABASE_URL="postgresql+asyncpg://postgres.xxx:PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres"
```

### Install Dependencies

```bash
# Quick install with uv
uv add asyncpg greenlet
```

Or in `pyproject.toml`:
```toml
dependencies = [
    "openai-agents[sqlalchemy]>=0.6.5",
    "asyncpg>=0.30.0",
    "greenlet>=3.0.0",
]
```
Then run `uv sync`.

### Initialize Database

```python
from core.database import init_db

async def main():
    await init_db()  # Creates tables if they don't exist
```

### Save Data

```python
from core.database import save_incident, save_feedback

# In your tool function
db_incident = await save_incident(incident)
print(f"Saved with ID: {db_incident.id}")
```

---

## Future Enhancement Considerations

### Schema Migrations (Editing Tables)

`init_db()` only creates tables that **don't exist** - it won't modify existing tables to add new columns.

**To add columns to existing tables:**

```sql
-- Option 1: Manually add columns via Supabase SQL Editor
ALTER TABLE incidents ADD COLUMN session_id VARCHAR(255);
CREATE INDEX idx_incidents_session_id ON incidents(session_id);

-- Option 2: Drop and recreate (loses data)
DROP TABLE IF EXISTS incidents;
-- Then run init_db() again
```

**For production:** Consider using [Alembic](https://alembic.sqlalchemy.org/) for proper migration management.

---

### Foreign Keys

Foreign keys link tables together (the lines in schema visualizers). They ensure data integrity - e.g., an incident's `session_id` must exist in `agent_sessions`.

```python
# Example: Adding a foreign key in SQLAlchemy
from sqlalchemy import ForeignKey

session_id: Mapped[str] = mapped_column(
    String(255), 
    ForeignKey("agent_sessions.session_id", ondelete="CASCADE"),
    index=True
)
```

**Trade-offs:**
- Pros: Data integrity, automatic cascading deletes, clearer relationships
- Cons: More constraints, requires parent records to exist first

---

### Row Level Security (RLS)

Supabase supports RLS to restrict data access at the database level. Useful when exposing the database to untrusted clients.

**Example policies:**
```sql
-- Users can only see their own incidents
CREATE POLICY "Users see own incidents" ON incidents
  FOR SELECT USING (session_id = current_user_session_id());

-- Users can only insert their own incidents  
CREATE POLICY "Users insert own incidents" ON incidents
  FOR INSERT WITH CHECK (session_id = current_user_session_id());
```

**When to consider RLS:**
- Multi-tenant applications
- Direct client access to database (e.g., Supabase JS client)
- Sensitive data that needs row-level access control

**Resources:** [Supabase RLS Guide](https://supabase.com/docs/guides/auth/row-level-security)

---

## Further Reading

- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [OpenAI Agents SDK - SQLAlchemy Sessions](https://openai.github.io/openai-agents-python/sessions/sqlalchemy_session/)
- [Supabase Documentation](https://supabase.com/docs)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
