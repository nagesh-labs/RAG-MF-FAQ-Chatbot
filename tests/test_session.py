"""
Comprehensive Unit Tests for Multi-Thread Session & State Management.
Validates:
1. SQLite Database Schema Initialization & Foreign Key Cascading.
2. Thread CRUD Operations (Create, Read, List, Delete).
3. Complete Thread Isolation (zero context leakage across thread_id).
4. Sliding Conversational Memory Window (last 2 turns / 4 messages max).
5. Antecedent Pronoun Resolution ("What is its exit load?").
6. Scheme Switching within a thread ("What about HDFC Top 100?").
"""

import asyncio
from pathlib import Path
import pytest
import tempfile
import uuid

from src.session.thread_manager import ThreadManager, MessageModel, ThreadSummary


import gc


@pytest.fixture
def temp_manager(tmp_path: Path):
    """Create a temporary ThreadManager instance with an isolated SQLite DB."""
    db_path = tmp_path / f"test_threads_{uuid.uuid4().hex[:8]}.db"
    manager = ThreadManager(db_path=db_path)
    yield manager
    gc.collect()


# =====================================================================
# 1. Thread CRUD Tests (Async)
# =====================================================================

def test_create_and_get_thread(temp_manager: ThreadManager):
    """Verify thread creation and retrieval."""
    async def run():
        thread = await temp_manager.create_thread(title="My Research Thread")
        assert thread.thread_id is not None
        assert thread.title == "My Research Thread"
        assert thread.message_count == 0

        fetched = await temp_manager.get_thread(thread.thread_id)
        assert fetched is not None
        assert fetched.thread_id == thread.thread_id
        assert fetched.title == "My Research Thread"
        assert fetched.message_count == 0

    asyncio.run(run())


def test_list_threads_sorted_by_activity(temp_manager: ThreadManager):
    """Verify threads are listed in descending order of last update."""
    async def run():
        t1 = await temp_manager.create_thread(title="Thread 1")
        await asyncio.sleep(0.01)
        t2 = await temp_manager.create_thread(title="Thread 2")

        threads = await temp_manager.list_threads()
        assert len(threads) == 2
        # Most recent first
        assert threads[0].thread_id == t2.thread_id
        assert threads[1].thread_id == t1.thread_id

        # Now add message to Thread 1; it should become the most recent
        await temp_manager.add_message(t1.thread_id, role="user", content="New query in thread 1")
        threads_updated = await temp_manager.list_threads()
        assert threads_updated[0].thread_id == t1.thread_id

    asyncio.run(run())


def test_delete_thread_cascades_messages(temp_manager: ThreadManager):
    """Verify thread deletion removes the thread and all associated messages."""
    async def run():
        t = await temp_manager.create_thread(title="Thread to Delete")
        await temp_manager.add_message(t.thread_id, role="user", content="Question 1")
        await temp_manager.add_message(t.thread_id, role="assistant", content="Answer 1")

        history = await temp_manager.get_thread_history(t.thread_id)
        assert len(history) == 2

        deleted = await temp_manager.delete_thread(t.thread_id)
        assert deleted is True

        # Thread and messages should be gone
        fetched = await temp_manager.get_thread(t.thread_id)
        assert fetched is None
        empty_history = await temp_manager.get_thread_history(t.thread_id)
        assert len(empty_history) == 0

    asyncio.run(run())


# =====================================================================
# 2. Thread Isolation Tests
# =====================================================================

def test_thread_state_isolation(temp_manager: ThreadManager):
    """Verify strict isolation: messages in Thread A never appear in Thread B."""
    async def run():
        thread_a = await temp_manager.create_thread(title="Thread A - Mid Cap")
        thread_b = await temp_manager.create_thread(title="Thread B - Silver ETF")

        # Add messages to Thread A
        await temp_manager.add_message(
            thread_a.thread_id,
            role="user",
            content="What is the expense ratio for HDFC Mid-Cap?",
            source_url="https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        )
        await temp_manager.add_message(
            thread_a.thread_id,
            role="assistant",
            content="Expense ratio is 0.70%.",
            source_url="https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        )

        # Add messages to Thread B
        await temp_manager.add_message(
            thread_b.thread_id,
            role="user",
            content="What is the lock-in for HDFC Silver ETF FoF?",
            source_url="https://groww.in/mutual-funds/hdfc-silver-etf-fof-direct-growth",
        )

        # Verify Thread A history
        history_a = await temp_manager.get_thread_history(thread_a.thread_id)
        assert len(history_a) == 2
        for msg in history_a:
            assert "Silver" not in msg.content

        # Verify Thread B history
        history_b = await temp_manager.get_thread_history(thread_b.thread_id)
        assert len(history_b) == 1
        assert "Mid-Cap" not in history_b[0].content

        # Message counts on summaries
        info_a = await temp_manager.get_thread(thread_a.thread_id)
        info_b = await temp_manager.get_thread(thread_b.thread_id)
        assert info_a.message_count == 2
        assert info_b.message_count == 1

    asyncio.run(run())


# =====================================================================
# 3. Conversational Memory Windowing Tests
# =====================================================================

def test_recent_conversation_window(temp_manager: ThreadManager):
    """Verify sliding window retrieves at most max_turns * 2 messages."""
    async def run():
        t = await temp_manager.create_thread(title="Multi-Turn Thread")

        # Add 6 messages (3 full turns)
        for i in range(1, 4):
            await temp_manager.add_message(t.thread_id, role="user", content=f"Turn {i} question")
            await temp_manager.add_message(t.thread_id, role="assistant", content=f"Turn {i} answer")

        full_history = await temp_manager.get_thread_history(t.thread_id)
        assert len(full_history) == 6

        # Window with max_turns=2 should retrieve only the last 4 messages (Turns 2 and 3)
        window = await temp_manager.get_recent_conversation_window(t.thread_id, max_turns=2)
        assert len(window) == 4
        assert window[0].content == "Turn 2 question"
        assert window[1].content == "Turn 2 answer"
        assert window[2].content == "Turn 3 question"
        assert window[3].content == "Turn 3 answer"

    asyncio.run(run())


# =====================================================================
# 4. Antecedent Pronoun Resolution Tests
# =====================================================================

def test_antecedent_pronoun_resolution(temp_manager: ThreadManager):
    """Verify follow-up queries with pronouns resolve correctly from immediate prior turn."""
    async def run():
        t = await temp_manager.create_thread(title="Follow-up test")

        # Turn 1: User asks about HDFC Mid-Cap
        await temp_manager.add_message(
            t.thread_id,
            role="user",
            content="What is the expense ratio for HDFC Mid-Cap Opportunities Fund?",
        )
        await temp_manager.add_message(
            t.thread_id,
            role="assistant",
            content="HDFC Mid-Cap Opportunities Fund Direct-Growth has an expense ratio of 0.70%.",
            source_url="https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        )

        # Turn 2: User asks follow-up with pronoun "its"
        resolved_query, scheme_id = await temp_manager.resolve_antecedent_context(
            query="What is its exit load?",
            thread_id=t.thread_id,
        )

        assert scheme_id == "hdfc-mid-cap-fund-direct-growth"
        assert "HDFC Mid-Cap" in resolved_query
        assert "exit load" in resolved_query.lower()

    asyncio.run(run())


def test_scheme_switching_within_thread(temp_manager: ThreadManager):
    """Verify switching schemes within the same thread overrides previous turn context."""
    async def run():
        t = await temp_manager.create_thread(title="Scheme switch test")

        # Turn 1: Discuss Small Cap
        await temp_manager.add_message(
            t.thread_id,
            role="user",
            content="What is the exit load for HDFC Small Cap Fund?",
        )
        await temp_manager.add_message(
            t.thread_id,
            role="assistant",
            content="The exit load is 1% if redeemed within 1 year.",
            source_url="https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
        )

        # Turn 2: Switch to HDFC Top 100 Large Cap
        resolved_query, scheme_id = await temp_manager.resolve_antecedent_context(
            query="What is the benchmark index for HDFC Top 100?",
            thread_id=t.thread_id,
        )

        # Must resolve to Top 100 (large cap), NOT the previous small cap
        assert scheme_id == "hdfc-large-cap-fund-direct-growth"
        assert "Top 100" in resolved_query

    asyncio.run(run())


def test_pronoun_without_prior_context_returns_none(temp_manager: ThreadManager):
    """Verify pronoun in an empty thread does not hallucinate a scheme."""
    async def run():
        empty_thread = await temp_manager.create_thread(title="Fresh Thread")

        resolved_query, scheme_id = await temp_manager.resolve_antecedent_context(
            query="What is its exit load?",
            thread_id=empty_thread.thread_id,
        )

        assert scheme_id is None
        assert resolved_query == "What is its exit load?"

    asyncio.run(run())


# =====================================================================
# 5. Synchronous Methods Tests
# =====================================================================

def test_sync_thread_operations(temp_manager: ThreadManager):
    """Verify synchronous wrappers operate correctly."""
    t = temp_manager.create_thread_sync(title="Sync Thread")
    assert t.title == "Sync Thread"

    msg = temp_manager.add_message_sync(t.thread_id, role="user", content="Sync query")
    assert msg.content == "Sync query"

    history = temp_manager.get_thread_history_sync(t.thread_id)
    assert len(history) == 1
    assert history[0].content == "Sync query"

    deleted = temp_manager.delete_thread_sync(t.thread_id)
    assert deleted is True
