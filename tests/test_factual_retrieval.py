"""
Task 7.1: Comprehensive Factual Retrieval Test Suite.
Validates answers across all 5 target HDFC schemes and operational guides for:
- Expense Ratio
- Exit Load
- Minimum SIP
- Lock-in period
- Riskometer rating
- Benchmark index
- Statement download and capital gains workflow
"""

import pytest
from src.rag.retriever import retrieve_context, get_canonical_citation_for_scheme
from src.rag.generator import generate_answer
from src.config import TARGET_SCHEMES


TARGET_SCHEME_KEYS = list(TARGET_SCHEMES.keys())


@pytest.mark.parametrize("scheme_key", TARGET_SCHEME_KEYS)
def test_expense_ratio_retrieval(scheme_key):
    """Verify expense ratio retrieval and accuracy across all 5 schemes."""
    meta = TARGET_SCHEMES[scheme_key]
    query = f"What is the expense ratio for {meta.scheme_name}?"
    
    chunks, detected_id = retrieve_context(query)
    assert detected_id == scheme_key
    assert len(chunks) > 0
    
    answer = generate_answer(query, chunks, primary_scheme_id=detected_id)
    assert meta.source_url in answer
    assert "expense ratio" in answer.lower()
    assert "%" in answer


@pytest.mark.parametrize("scheme_key", TARGET_SCHEME_KEYS)
def test_exit_load_retrieval(scheme_key):
    """Verify exit load retrieval and accuracy across all 5 schemes."""
    meta = TARGET_SCHEMES[scheme_key]
    query = f"What is the exit load of {meta.scheme_name}?"
    
    chunks, detected_id = retrieve_context(query)
    assert detected_id == scheme_key
    assert len(chunks) > 0
    
    answer = generate_answer(query, chunks, primary_scheme_id=detected_id)
    assert meta.source_url in answer
    assert "exit load" in answer.lower()


@pytest.mark.parametrize("scheme_key", TARGET_SCHEME_KEYS)
def test_minimum_sip_retrieval(scheme_key):
    """Verify minimum SIP retrieval and accuracy across all 5 schemes."""
    meta = TARGET_SCHEMES[scheme_key]
    query = f"What is the minimum SIP investment for {meta.scheme_name}?"
    
    chunks, detected_id = retrieve_context(query)
    assert detected_id == scheme_key
    assert len(chunks) > 0
    
    answer = generate_answer(query, chunks, primary_scheme_id=detected_id)
    assert meta.source_url in answer
    assert ("sip" in answer.lower() or "minimum" in answer.lower())
    assert "100" in answer


@pytest.mark.parametrize("scheme_key", TARGET_SCHEME_KEYS)
def test_lock_in_period_retrieval(scheme_key):
    """Verify lock-in period retrieval across all 5 schemes (nil lock-in)."""
    meta = TARGET_SCHEMES[scheme_key]
    query = f"What is the lock-in period for {meta.scheme_name}?"
    
    chunks, detected_id = retrieve_context(query)
    assert detected_id == scheme_key
    assert len(chunks) > 0
    
    answer = generate_answer(query, chunks, primary_scheme_id=detected_id)
    assert meta.source_url in answer
    norm_answer = answer.replace("\u2011", "-").lower()
    assert ("nil" in norm_answer or "open-ended" in norm_answer or "no lock-in" in norm_answer or "lock-in" in norm_answer or "lock in" in norm_answer)


@pytest.mark.parametrize("scheme_key", TARGET_SCHEME_KEYS)
def test_riskometer_rating_retrieval(scheme_key):
    """Verify riskometer rating retrieval across all 5 schemes."""
    meta = TARGET_SCHEMES[scheme_key]
    query = f"What is the riskometer rating of {meta.scheme_name}?"
    
    chunks, detected_id = retrieve_context(query)
    assert detected_id == scheme_key
    assert len(chunks) > 0
    
    answer = generate_answer(query, chunks, primary_scheme_id=detected_id)
    assert meta.source_url in answer
    assert "risk" in answer.lower()


@pytest.mark.parametrize("scheme_key", TARGET_SCHEME_KEYS)
def test_benchmark_index_retrieval(scheme_key):
    """Verify benchmark index retrieval across all 5 schemes."""
    meta = TARGET_SCHEMES[scheme_key]
    query = f"What is the benchmark index for {meta.scheme_name}?"
    
    chunks, detected_id = retrieve_context(query)
    assert detected_id == scheme_key
    assert len(chunks) > 0
    
    answer = generate_answer(query, chunks, primary_scheme_id=detected_id)
    assert meta.source_url in answer
    assert "benchmark" in answer.lower() or "nifty" in answer.lower() or "bse" in answer.lower() or "silver" in answer.lower()


def test_statement_download_workflow():
    """Verify operational workflow retrieval for mutual fund account statement."""
    query = "How do I download my mutual fund account statement on Groww?"
    chunks, detected_id = retrieve_context(query)
    assert len(chunks) > 0
    
    answer = generate_answer(query, chunks, primary_scheme_id=detected_id)
    assert "https://groww.in/mutual-funds" in answer
    assert ("statement" in answer.lower() or "reports" in answer.lower() or "profile" in answer.lower())


def test_capital_gains_download_workflow():
    """Verify operational workflow retrieval for tax / capital gains report."""
    query = "How can I download the capital gains statement for tax filing?"
    chunks, detected_id = retrieve_context(query)
    assert len(chunks) > 0
    
    answer = generate_answer(query, chunks, primary_scheme_id=detected_id)
    assert "https://groww.in/mutual-funds" in answer
    assert ("capital gains" in answer.lower() or "tax" in answer.lower() or "reports" in answer.lower())


@pytest.mark.parametrize("scheme_key", TARGET_SCHEME_KEYS)
def test_nav_retrieval(scheme_key):
    """Verify NAV retrieval across all 5 schemes."""
    meta = TARGET_SCHEMES[scheme_key]
    query = f"What is the current NAV of {meta.scheme_name}?"
    
    chunks, detected_id = retrieve_context(query)
    assert detected_id == scheme_key
    assert len(chunks) > 0
    
    answer = generate_answer(query, chunks, primary_scheme_id=detected_id)
    assert meta.source_url in answer
    assert ("nav" in answer.lower() or "₹" in answer or "net asset value" in answer.lower())


@pytest.mark.parametrize("scheme_key", TARGET_SCHEME_KEYS)
def test_fund_rating_retrieval(scheme_key):
    """Verify fund rating retrieval across all 5 schemes."""
    meta = TARGET_SCHEMES[scheme_key]
    query = f"What is the fund rating for {meta.scheme_name}?"
    
    chunks, detected_id = retrieve_context(query)
    assert detected_id == scheme_key
    assert len(chunks) > 0
    
    answer = generate_answer(query, chunks, primary_scheme_id=detected_id)
    assert meta.source_url in answer
    assert ("star" in answer.lower() or "rated" in answer.lower() or "rating" in answer.lower())


@pytest.mark.parametrize("scheme_key", TARGET_SCHEME_KEYS)
def test_returns_retrieval(scheme_key):
    """Verify historical returns retrieval across all 5 schemes."""
    meta = TARGET_SCHEMES[scheme_key]
    query = f"What is the 1-year return of {meta.scheme_name}?"
    
    chunks, detected_id = retrieve_context(query)
    assert detected_id == scheme_key
    assert len(chunks) > 0
    
    answer = generate_answer(query, chunks, primary_scheme_id=detected_id)
    assert meta.source_url in answer
    assert ("%" in answer or "return" in answer.lower())


@pytest.mark.parametrize("scheme_key", TARGET_SCHEME_KEYS)
def test_holdings_retrieval(scheme_key):
    """Verify portfolio holdings retrieval across all 5 schemes."""
    meta = TARGET_SCHEMES[scheme_key]
    query = f"What are the top portfolio holdings of {meta.scheme_name}?"
    
    chunks, detected_id = retrieve_context(query)
    assert detected_id == scheme_key
    assert len(chunks) > 0
    
    answer = generate_answer(query, chunks, primary_scheme_id=detected_id)
    assert meta.source_url in answer
    assert ("holding" in answer.lower() or "bank" in answer.lower() or "silver" in answer.lower() or "ltd" in answer.lower() or "repo" in answer.lower())


@pytest.mark.parametrize("scheme_key", TARGET_SCHEME_KEYS)
def test_turnover_launch_retrieval(scheme_key):
    """Verify portfolio turnover and launch date retrieval across all 5 schemes."""
    meta = TARGET_SCHEMES[scheme_key]
    query = f"When was {meta.scheme_name} launched and what is its portfolio turnover?"
    
    chunks, detected_id = retrieve_context(query)
    assert detected_id == scheme_key
    assert len(chunks) > 0
    
    answer = generate_answer(query, chunks, primary_scheme_id=detected_id)
    assert meta.source_url in answer
    assert ("launch" in answer.lower() or "turnover" in answer.lower() or "2013" in answer or "2021" in answer or "2022" in answer)

