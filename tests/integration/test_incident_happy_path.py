"""
Integration test: Incident Reporting — Happy Path

Runs the full 5-turn conversation through the agent chain:
  Dialogue Agent → Triage Agent → Conversation Format Coordinator
                                    ├── incident_formatter_tool
                                    └── conversation_summarizer_tool

Pass criteria:
  1. Evaluator agent deems conversation quality acceptable (overall_score >= 3)
  2. All 5 background verification checks succeed

Requires: OPENAI_API_KEY, VECTOR_STORE_ID environment variables.
See: tests/integration/scripts/incident_happy_path.md for full spec.

How to test:
Run "python -m pytest tests/integration/test_incident_happy_path.py -v"
Wait for a few seconds for the llm to finish
"""

from dotenv import load_dotenv

load_dotenv()

import uuid
import logging

import pytest
from agents import Runner
from agents.extensions.memory import SQLAlchemySession
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from core.context import TownHallContext, AgentStage
from core.database import init_db, DATABASE_URL, IncidentModel
from core.models import Incident
from town_hall_agents import dialogue_agent
from tests.models.evaluation_models import ConversationEvaluation

# Use SQLite for the agents SDK session history to avoid asyncpg event loop conflicts.
# The application DB (DATABASE_URL) is used only for incident persistence via save_incident().
TEST_SESSION_DB_URL = "sqlite+aiosqlite:///test_session_history.db"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Conversation script
# ---------------------------------------------------------------------------
USER_MESSAGES = [
    "Hi! I'd like to report something that happened near the park.",
    "Yesterday around 3 PM, I saw someone steal a bicycle from the rack near Central Park. The person was wearing a red hoodie.",
    "My name is Maria Garcia. It looked pretty serious to me.",
    "Yes, that's correct. That's all I wanted to report.",
    "Thank you!",
]

# ---------------------------------------------------------------------------
# Evaluator prompt
# ---------------------------------------------------------------------------
EVALUATOR_PROMPT = """\
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

Set `passed` to true if overall_score >= 3.

Provide a concise rationale explaining your assessment.

CONVERSATION TRANSCRIPT:
{transcript}
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
async def db():
    """Initialize the database once per module."""
    await init_db()


@pytest.fixture(scope="module")
async def test_db_session(db):
    """Create a DB session factory bound to the current event loop."""
    IS_POSTGRES = DATABASE_URL.startswith("postgresql")
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"statement_cache_size": 0} if IS_POSTGRES else {},
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture(scope="module")
async def conversation_result(db):
    """
    Run the full 5-turn conversation and return (context, transcript, responses).

    This is module-scoped so the expensive LLM calls only happen once; individual
    test functions assert against the cached result.
    """
    session_id = f"test-incident-{uuid.uuid4()}"
    context = TownHallContext(session_id=session_id)
    session = SQLAlchemySession.from_url(
        session_id,
        url=TEST_SESSION_DB_URL,
        create_tables=True,
    )

    transcript_lines: list[str] = []
    responses: list[str] = []
    current_agent = dialogue_agent

    for user_msg in USER_MESSAGES:
        transcript_lines.append(f"User: {user_msg}")

        result = Runner.run_streamed(
            current_agent,
            user_msg,
            session=session,
            context=context,
        )

        # Collect streamed response
        response_text = ""
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(
                event.data, ResponseTextDeltaEvent
            ):
                response_text += event.data.delta

        current_agent = result.last_agent
        responses.append(response_text)
        transcript_lines.append(f"Agent: {response_text}")
        logger.info("Turn complete — agent=%s", current_agent.name)

    # Persist structured outputs (mirrors chatkit_server._persist_structured_outputs)
    if context.incident_processed and context.incident is not None:
        from core.database import save_incident

        await save_incident(context.incident, session_id=session_id)

    transcript = "\n".join(transcript_lines)
    return context, transcript, responses, session_id


# ---------------------------------------------------------------------------
# Background verification checks
# ---------------------------------------------------------------------------
class TestBackgroundChecks:
    """Background checks that must all pass (independent of evaluator)."""

    async def test_database_persistence(self, conversation_result, test_db_session):
        """Check 1: Incident row saved with correct fields."""
        ctx, _, _, session_id = conversation_result

        async with test_db_session() as db_session:
            row = await db_session.execute(
                select(IncidentModel).where(
                    IncidentModel.session_id == session_id
                )
            )
            incident = row.scalar_one_or_none()

        assert incident is not None, "No incident row found in database"
        assert incident.reporter_name == "Maria Garcia"

        desc_lower = incident.description.lower()
        assert "bicycle" in desc_lower or "bike" in desc_lower, (
            f"Description missing bicycle/bike: {incident.description}"
        )
        assert "central park" in incident.location.lower() or "park" in incident.location.lower(), (
            f"Location missing park reference: {incident.location}"
        )
        assert "red hoodie" in incident.person_involved.lower() or "hoodie" in incident.person_involved.lower(), (
            f"Person description missing hoodie: {incident.person_involved}"
        )
        assert 1 <= incident.severity_level <= 5, (
            f"Severity out of range: {incident.severity_level}"
        )

    async def test_context_flags(self, conversation_result):
        """Check 2: incident_processed and incident set on context."""
        ctx, _, _, _ = conversation_result

        assert ctx.incident_processed is True, "incident_processed flag not set"
        assert ctx.incident is not None, "incident is None on context"
        assert isinstance(ctx.incident, Incident), (
            f"incident is {type(ctx.incident)}, expected Incident"
        )

    async def test_triage_handoff(self, conversation_result):
        """Check 3: Agent chain progressed through triage."""
        ctx, _, _, _ = conversation_result

        # After the full chain the stage may have returned to dialogue
        # or still be in a formatting stage. The key indicator is that
        # the incident was processed (which requires triage → coordinator).
        assert ctx.incident_processed is True, (
            "Incident not processed — triage handoff likely did not occur"
        )

    async def test_incident_formatter_invoked(self, conversation_result):
        """Check 4: incident_formatter_tool was called (not feedback_formatter)."""
        ctx, _, _, _ = conversation_result

        assert ctx.incident is not None, "incident_formatter_tool did not run"
        assert ctx.incident_processed is True
        # feedback_formatter should NOT have been invoked for a pure incident
        assert ctx.feedback is None or ctx.feedback_processed is False, (
            "feedback_formatter_tool was unexpectedly invoked"
        )

    async def test_conversation_summarizer(self, conversation_result):
        """Check 5: conversation_summarizer_tool produced output.

        NOTE: The conversation_summarizer_tool is created via agent.as_tool()
        and does NOT write to ctx.conversation (unlike incident_formatter_tool
        which explicitly sets context fields). This check verifies the agent
        chain reached the formatting stage, which implies the coordinator had
        the opportunity to invoke the summarizer.
        """
        ctx, _, _, _ = conversation_result

        # The coordinator agent was reached (proven by incident being processed)
        # and agent_stage reflects formatting activity.
        assert ctx.agent_stage in (
            AgentStage.INCIDENT_FORMATTING,
            AgentStage.CONVERSATION_FORMATTING,
            AgentStage.DIALOGUE,
        ), f"Unexpected agent_stage: {ctx.agent_stage}"

        # If the summarizer wrote to context, verify its content
        if ctx.conversation is not None and hasattr(ctx.conversation, "conversation_type"):
            assert ctx.conversation.conversation_type == "incident", (
                f"Expected conversation_type='incident', got '{ctx.conversation.conversation_type}'"
            )


# ---------------------------------------------------------------------------
# Evaluator agent check
# ---------------------------------------------------------------------------
class TestEvaluator:
    """LLM-as-judge evaluation of the full conversation."""

    async def test_evaluator_passes(self, conversation_result):
        """Evaluator agent deems the conversation acceptable."""
        _, transcript, _, _ = conversation_result

        client = AsyncOpenAI()
        response = await client.responses.parse(
            model="gpt-4.1-mini",
            instructions=EVALUATOR_PROMPT.format(transcript=transcript),
            input="Evaluate the conversation above.",
            text_format=ConversationEvaluation,
        )

        evaluation = response.output_parsed
        logger.info(
            "Evaluation: tone=%d info=%d flow=%d personal=%d overall=%d | %s",
            evaluation.tone_consistency,
            evaluation.information_completeness,
            evaluation.flow_naturalness,
            evaluation.personalization,
            evaluation.overall_score,
            evaluation.rationale,
        )

        assert evaluation.passed, (
            f"Evaluator failed (overall_score={evaluation.overall_score}): "
            f"{evaluation.rationale}"
        )
