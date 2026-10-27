"""
Task 7.4: Multi-Thread Concurrency and State Isolation Test Suite.
Validates:
1. Simultaneous asynchronous thread creation and message operations.
2. Concurrent antecedent pronoun resolution across multiple threads without cross-thread context leakage.
3. Database consistency under concurrent read/write workloads.
"""

import asyncio
import gc
from pathlib import Path
import pytest
import uuid

from src.session.thread_manager import ThreadManager
from src.rag.retriever import retrieve_context
from src.rag.generator import generate_answer


@pytest.fixture
def isolated_manager(tmp_path: Path):
    """Temporary ThreadManager instance."""
    db_file = tmp_path / f"test_concurrent_{uuid.uuid4().hex[:8]}.db"
    manager = ThreadManager(db_path=db_file)
    yield manager
    gc.collect()


def test_concurrent_thread_creation_and_messaging(isolated_manager: ThreadManager):
    """Verify that multiple threads can be created and messaged concurrently without conflicts."""
    async def run():
        # Create 10 threads concurrently
        thread_ids = await asyncio.gather(*[
            isolated_manager.create_thread(title=f"Concurrent Thread {i}")
            for i in range(10)
        ])
        assert len(thread_ids) == 10
        assert len(set(t.thread_id for t in thread_ids)) == 10

        # Concurrently add messages to all 10 threads
        async def add_turn(tid, idx):
            await isolated_manager.add_message(tid, "user", f"Question in thread {idx}")
            await isolated_manager.add_message(tid, "assistant", f"Answer in thread {idx}")

        await asyncio.gather(*[
            add_turn(t.thread_id, i) for i, t in enumerate(thread_ids)
        ])

        # Verify message count for each thread is exactly 2
        for t in thread_ids:
            history = await isolated_manager.get_thread_history(t.thread_id)
            assert len(history) == 2
            assert history[0].role == "user"
            assert history[1].role == "assistant"

    asyncio.run(run())


def test_concurrent_antecedent_pronoun_resolution(isolated_manager: ThreadManager):
    """
    Verify concurrent follow-up questions with antecedent pronouns ("its benchmark")
    across distinct threads resolve to each thread's respective scheme with zero leakage.
    """
    async def run():
        # Step 1: Create 3 distinct threads
        t_midcap = await isolated_manager.create_thread(title="MidCap Thread")
        t_silver = await isolated_manager.create_thread(title="Silver Thread")
        t_smallcap = await isolated_manager.create_thread(title="SmallCap Thread")

        # Step 2: Seed each thread with a scheme-specific query
        await isolated_manager.add_message(
            t_midcap.thread_id, "user", "What is the exit load for HDFC Mid-Cap Opportunities Fund?"
        )
        await isolated_manager.add_message(
            t_midcap.thread_id, "assistant", "The exit load is 1% if redeemed within 1 year.",
            source_url="https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
        )

        await isolated_manager.add_message(
            t_silver.thread_id, "user", "What is the exit load for HDFC Silver ETF FoF?"
        )
        await isolated_manager.add_message(
            t_silver.thread_id, "assistant", "The exit load is 1% if redeemed within 15 days.",
            source_url="https://groww.in/mutual-funds/hdfc-silver-etf-fof-direct-growth"
        )

        await isolated_manager.add_message(
            t_smallcap.thread_id, "user", "What is the exit load for HDFC Small Cap Fund?"
        )
        await isolated_manager.add_message(
            t_smallcap.thread_id, "assistant", "The exit load is 1% if redeemed within 1 year.",
            source_url="https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth"
        )

        # Step 3: Concurrently issue pronoun follow-ups in all three threads
        follow_up_query = "What is its benchmark index?"
        
        res_midcap, res_silver, res_smallcap = await asyncio.gather(
            isolated_manager.resolve_antecedent_context(follow_up_query, t_midcap.thread_id),
            isolated_manager.resolve_antecedent_context(follow_up_query, t_silver.thread_id),
            isolated_manager.resolve_antecedent_context(follow_up_query, t_smallcap.thread_id),
        )

        # Step 4: Verify resolution
        resolved_text_mid, sid_mid = res_midcap
        resolved_text_sil, sid_sil = res_silver
        resolved_text_sma, sid_sma = res_smallcap

        assert sid_mid == "hdfc-mid-cap-fund-direct-growth"
        assert "HDFC Mid-Cap Opportunities Fund" in resolved_text_mid

        assert sid_sil == "hdfc-silver-etf-fof-direct-growth"
        assert "HDFC Silver ETF" in resolved_text_sil

        assert sid_sma == "hdfc-small-cap-fund-direct-growth"
        assert "HDFC Small Cap Fund" in resolved_text_sma

        # Step 5: Verify concurrent RAG generation for each
        chunks_mid, _ = retrieve_context(resolved_text_mid)
        chunks_sil, _ = retrieve_context(resolved_text_sil)
        chunks_sma, _ = retrieve_context(resolved_text_sma)

        ans_mid = generate_answer(resolved_text_mid, chunks_mid, primary_scheme_id=sid_mid)
        ans_sil = generate_answer(resolved_text_sil, chunks_sil, primary_scheme_id=sid_sil)
        ans_sma = generate_answer(resolved_text_sma, chunks_sma, primary_scheme_id=sid_sma)

        # Verify Mid-Cap benchmark
        assert "nifty midcap 150" in ans_mid.lower()
        assert "silver" not in ans_mid.lower()

        # Verify Silver ETF benchmark
        assert "silver" in ans_sil.lower()
        assert "midcap" not in ans_sil.lower()

        # Verify Small Cap benchmark
        assert "250 smallcap" in ans_sma.lower() or "bse" in ans_sma.lower()
        assert "silver" not in ans_sma.lower()

    asyncio.run(run())
