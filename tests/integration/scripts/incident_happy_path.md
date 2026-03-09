# Integration Test: Incident Reporting — Happy Path

## 1. Overview

This integration test validates the end-to-end **"Report an Incident"** workflow through the Digital Town Hall agent system. It verifies that a citizen can report an incident through natural conversation and that the system correctly extracts, formats, and persists structured incident data.

### Agent Chain

```
Dialogue Agent → Triage Agent → Conversation Format Coordinator Agent
                                    ├── incident_formatter_tool
                                    └── conversation_summarizer_tool
```

### Pass Criteria

The test **passes** if and only if:
1. The **evaluator agent** deems the conversation quality acceptable (`passed == True`)
2. All **5 background verification checks** succeed

---

## 2. Prerequisites

| Requirement | Details |
|---|---|
| `OPENAI_API_KEY` | Valid OpenAI API key set in environment |
| `VECTOR_STORE_ID` | Valid vector store ID for the Dialogue Agent's file search tool |
| `DATABASE_URL` | Database connection string (SQLite or PostgreSQL) |
| Database initialized | `init_db()` called before test execution |
| Clean session | Fresh `session_id` with no prior conversation history |

---

## 3. Conversation Script

### Turn 1 — Greeting & Intent

**User message:**
> "Hi! I'd like to report something that happened near the park."

**Expected agent behavior:**
- **Dialogue Agent** responds in kawaii persona
- Acknowledges the user's intent to report
- Asks for more details about the incident

**Evaluator guidance:**
- Tone should be warm, approachable, and kawaii-consistent
- Agent should not jump to conclusions about the incident type

---

### Turn 2 — Incident Details

**User message:**
> "Yesterday around 3 PM, I saw someone steal a bicycle from the rack near Central Park. The person was wearing a red hoodie."

**Expected agent behavior:**
- **Dialogue Agent** captures key details: type (theft), date (yesterday ~3 PM), location (Central Park bike rack), person description (red hoodie)
- Asks for the reporter's name or any missing information
- Maintains kawaii tone while being respectful of the seriousness

**Evaluator guidance:**
- Agent should acknowledge the details provided
- Should ask for remaining required fields (reporter name, severity sense)
- Should not be dismissive of the incident

---

### Turn 3 — Reporter Identity & Confirmation

**User message:**
> "My name is Maria Garcia. It looked pretty serious to me."

**Expected agent behavior:**
- **Dialogue Agent** captures reporter name: Maria Garcia
- Summarizes the full incident back to the user for confirmation
- Uses the reporter's name in the response

**Evaluator guidance:**
- Personalization: agent should use "Maria" or "Maria Garcia" in response
- Summary should include all gathered details
- Should ask for explicit confirmation before proceeding

---

### Turn 4 — User Confirms

**User message:**
> "Yes, that's correct. That's all I wanted to report."

**Expected agent behavior:**
- **Dialogue Agent** recognizes conversation completion triggers ("that's correct", "that's all")
- Hands off to **Triage Agent**
- **Triage Agent** silently routes to **Conversation Format Coordinator Agent** (no user-visible output)
- **Conversation Format Coordinator Agent** invokes:
  1. `incident_formatter_tool` — extracts structured `Incident` from conversation
  2. `conversation_summarizer_tool` — produces `Conversation` summary

**Evaluator guidance:**
- Handoff should be seamless; user should not perceive internal routing
- Context flags should be set: `incident_processed == True`, `incident is not None`

---

### Turn 5 — Closing

**User message:**
> "Thank you!"

**Expected agent behavior:**
- **Dialogue Agent** (after handoff chain completes and returns) responds with a friendly closing
- Thanks the user, reassures that the report has been noted
- Maintains kawaii persona to the end

**Evaluator guidance:**
- Closing should feel natural and complete
- Agent should not ask for more information after the user said goodbye
- Kawaii tone should be consistent through the final message

---

## 4. Evaluator Agent Specification

### Evaluation Approach

The evaluator performs a **holistic assessment** of the full conversation transcript after all 5 turns complete. It does not evaluate turn-by-turn — it reviews the entire exchange as a whole.

### Structured Output Schema

The evaluator returns a `ConversationEvaluation` object as defined in `tests/models/evaluation_models.py`:

```python
class ConversationEvaluation(BaseModel):
    tone_consistency: int       # 1-5
    information_completeness: int  # 1-5
    flow_naturalness: int       # 1-5
    personalization: int        # 1-5
    overall_score: int          # 1-5
    rationale: str
    passed: bool                # True if overall_score >= 3
```

### Evaluator Prompt Template

```
You are an expert evaluator assessing a Digital Town Hall chatbot conversation.
The chatbot uses a kawaii (cute, friendly) persona while helping citizens
report incidents to their local government.

Review the following conversation transcript and evaluate it on these dimensions:

1. **Tone Consistency** (1-5): Did the agent maintain its kawaii persona throughout?
   Was it warm and approachable while still being respectful of serious topics?

2. **Information Completeness** (1-5): Did the agent gather all required incident fields?
   - incident_type, description, date_of_occurrence, location,
     person_involved, reporter_name, severity_level

3. **Flow Naturalness** (1-5): Did the conversation flow naturally? Was the user
   guided without feeling interrogated? Were transitions smooth?

4. **Personalization** (1-5): Did the agent use the reporter's name? Did it confirm
   details back to the user? Did responses feel tailored, not generic?

5. **Overall Score** (1-5): Holistic quality of the interaction.

Set `passed = True` if overall_score >= 3.

Provide a concise rationale explaining your assessment.

CONVERSATION TRANSCRIPT:
{transcript}
```

### Scoring Rubric

| Score | Meaning |
|---|---|
| **5** | Excellent — exceeds expectations, delightful interaction |
| **4** | Good — meets all requirements with minor room for improvement |
| **3** | Acceptable — meets minimum requirements, no major issues |
| **2** | Below expectations — missing key elements or tone breaks |
| **1** | Poor — fundamentally broken interaction |

---

## 5. Background Verification Checks

All 5 checks must pass independently of the evaluator score.

### Check 1: Database Persistence

**What to verify:** An `IncidentModel` row exists in the database for the test `session_id`.

**Query:**
```python
incident_row = await session.execute(
    select(IncidentModel).where(IncidentModel.session_id == session_id)
)
result = incident_row.scalar_one_or_none()
assert result is not None
```

**Field assertions:**
| Field | Expected |
|---|---|
| `incident_type` | Contains "theft" or "stolen" (non-deterministic phrasing) |
| `description` | Mentions bicycle, Central Park, red hoodie |
| `location` | Contains "Central Park" or "park" |
| `person_involved` | Mentions "red hoodie" |
| `reporter_name` | "Maria Garcia" |
| `severity_level` | Between 3 and 5 (agent-inferred) |
| `session_id` | Matches test session ID |

---

### Check 2: Context Flags

**What to verify:** After the agent run completes, the `TownHallContext` has the correct state.

```python
assert ctx.incident_processed is True
assert ctx.incident is not None
assert isinstance(ctx.incident, Incident)
```

---

### Check 3: Triage Handoff

**What to verify:** The agent chain progressed through the expected stages.

```python
# Verify agent_stage transitioned through triage
# The Triage Agent should have routed to Conversation Format Coordinator
assert ctx.agent_stage in (
    AgentStage.CONVERSATION_FORMATTING,
    AgentStage.INCIDENT_FORMATTING,
    AgentStage.DIALOGUE,  # returns to dialogue after chain completes
)
```

**Log verification:** Look for log entries indicating the Triage Agent handed off to the Conversation Format Coordinator Agent (not the Insights Agent).

---

### Check 4: incident_formatter_tool Invocation

**What to verify:** The `incident_formatter_tool` was called by the Conversation Format Coordinator Agent.

```python
# The incident_formatter_tool sets these context values:
assert ctx.incident is not None
assert ctx.incident_processed is True
# Verify it was NOT the feedback_formatter_tool that was invoked
assert ctx.feedback is None or ctx.feedback_processed is False
```

**Log verification:** Check for log entry: `"incident_formatter_tool_end type=%s severity=%s"`

---

### Check 5: Conversation Summarizer Output

**What to verify:** The `conversation_summarizer_tool` produced a valid `Conversation` object.

```python
assert ctx.conversation is not None
assert ctx.conversation.conversation_type == "incident"
assert ctx.conversation.turn_count >= 5
assert ctx.conversation.resolved is True
```

---

## 6. Pass/Fail Criteria

```
PASS = evaluator.passed == True
       AND check_database_persistence()
       AND check_context_flags()
       AND check_triage_handoff()
       AND check_incident_formatter_invocation()
       AND check_conversation_summarizer()

FAIL = evaluator.passed == False
       OR any background check fails
```

| Result | Condition |
|---|---|
| **PASS** | Evaluator `passed == True` AND all 5 background checks succeed |
| **FAIL** | Evaluator `passed == False` OR any background check fails |

When a test fails, the output should include:
- The evaluator's `rationale` string
- Which background check(s) failed and why
- The full conversation transcript for debugging

---

## 7. Expected Incident Output

```json
{
  "incident_type": "theft",
  "description": "A bicycle was stolen from the rack near Central Park. The suspect was wearing a red hoodie. The incident occurred around 3 PM.",
  "date_of_occurrence": "2026-03-08",
  "location": "Central Park bike rack",
  "person_involved": "Unknown individual wearing a red hoodie",
  "reporter_name": "Maria Garcia",
  "severity_level": 4
}
```

### Tolerance Notes

| Field | Tolerance |
|---|---|
| `incident_type` | Exact value may vary: "theft", "bicycle theft", "stolen property" |
| `description` | Free-text; must mention bicycle, Central Park, red hoodie |
| `date_of_occurrence` | Should be yesterday's date relative to test execution |
| `location` | Must reference Central Park; exact phrasing may vary |
| `person_involved` | Must mention red hoodie; phrasing is non-deterministic |
| `reporter_name` | Must be "Maria Garcia" (deterministic) |
| `severity_level` | Agent-inferred; expect 3-5 range for theft |

---

## 8. Agent Handoff Chain Diagram

```
┌─────────────────┐
│  User Message    │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐   Turns 1-3: Gathers incident details
│   Dialogue Agent    │   Kawaii persona, file_search tool
│   (dialogue stage)  │   Asks for: type, description, date,
└────────┬────────────┘   location, person, reporter name
         │
         │  Turn 4: User confirms → triggers handoff
         ▼
┌─────────────────────┐   Silent router — no user-visible output
│   Triage Agent      │   Routes based on conversation content:
│   (triage stage)    │   incident/feedback → Coordinator
└────────┬────────────┘   insights → Insights Agent
         │
         │  Detected incident content → hands off
         ▼
┌──────────────────────────────────┐
│  Conversation Format Coordinator │   Orchestrates formatting tools
│  (conversation_formatting stage) │   in strict order
└────────┬─────────────────────────┘
         │
         ├──▶ incident_formatter_tool
         │    ├── Runs nested Incident Formatter Agent
         │    ├── Extracts structured Incident from transcript
         │    ├── Sets ctx.incident = Incident(...)
         │    └── Sets ctx.incident_processed = True
         │
         ├──▶ conversation_summarizer_tool
         │    ├── Produces Conversation summary
         │    └── Sets ctx.conversation = Conversation(...)
         │
         │  Hands back to Dialogue Agent
         ▼
┌─────────────────────┐
│   Dialogue Agent    │   Turn 5: Friendly closing message
│   (dialogue stage)  │   Thanks user, confirms report noted
└─────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  _persist_structured_outputs │   Saves to database:
│  (after agent run ends)      │   save_incident(ctx.incident, session_id)
└─────────────────────────────┘
```

---

## Referenced Source Files

| File | Key Exports |
|---|---|
| `core/models.py` | `Incident`, `Feedback`, `Conversation` Pydantic models |
| `core/context.py` | `TownHallContext`, `AgentStage` enum |
| `core/database.py` | `save_incident()`, `IncidentModel` ORM model |
| `core/chatkit_server.py` | `_persist_structured_outputs()` method |
| `town_hall_agents/dialogue_agent.py` | Dialogue Agent with kawaii persona, `file_search` tool |
| `town_hall_agents/triage_agent.py` | Triage Agent — silent router |
| `town_hall_agents/conversation_format_coordinator_agent.py` | Coordinator with `incident_formatter_tool`, `conversation_summarizer_tool` |
| `town_hall_agents/incident_formatter_agent.py` | `incident_formatter_tool` function tool |
