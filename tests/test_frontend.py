"""
Unit and Integration Tests for Milestone RAG Frontend Application.
Tests:
1. Frontend Configuration and Starter Prompts.
2. Thread Management Integration.
3. Chat Processing via Dual-Mode Backend (API / In-Process Pipeline).
4. Permanent Disclaimer & Compliance Elements.
"""

import pytest
from frontend.app import (
    api_list_threads,
    api_create_thread,
    api_delete_thread,
    api_get_messages,
    api_send_message,
    STARTER_QUESTIONS,
    MANDATORY_DISCLAIMER,
    TARGET_SCHEMES,
)


def test_starter_questions_presence():
    """Verify minimum 3 starter questions are defined and factual."""
    assert len(STARTER_QUESTIONS) >= 3
    assert any("exit load" in q.lower() for q in STARTER_QUESTIONS)
    assert any("minimum sip" in q.lower() for q in STARTER_QUESTIONS)
    assert any("benchmark" in q.lower() for q in STARTER_QUESTIONS)


def test_mandatory_disclaimer_content():
    """Verify permanent disclaimer text satisfies SEBI requirements."""
    assert "Facts-only" in MANDATORY_DISCLAIMER
    assert "No investment advice" in MANDATORY_DISCLAIMER


def test_supported_schemes_count():
    """Verify all 5 schemes are present in frontend reference catalog."""
    assert len(TARGET_SCHEMES) == 5
    for scheme_id, meta in TARGET_SCHEMES.items():
        assert meta.scheme_name
        assert meta.source_url.startswith("https://groww.in/mutual-funds/")


def test_frontend_thread_management():
    """Verify thread creation, listing, history, and deletion."""
    thread_id = api_create_thread(title="Frontend Test Thread")
    assert thread_id is not None

    threads = api_list_threads()
    assert any(t["thread_id"] == thread_id for t in threads)

    messages = api_get_messages(thread_id)
    assert messages == []

    deleted = api_delete_thread(thread_id)
    assert deleted is True


def test_frontend_send_factual_message():
    """Verify sending a factual message through the frontend pipeline."""
    thread_id = api_create_thread(title="Factual Test")
    try:
        query = "What is the exit load for HDFC Small Cap Fund Direct Growth?"
        res = api_send_message(query=query, thread_id=thread_id)

        assert res["is_refusal"] is False
        assert res["intent"] == "FACTUAL"
        assert "exit load" in res["answer"].lower() or "1.00%" in res["answer"]
        assert "groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth" in res["source_url"]

        # History should now contain 2 messages (user turn + assistant response)
        history = api_get_messages(thread_id)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
    finally:
        api_delete_thread(thread_id)


def test_frontend_send_advisory_message():
    """Verify sending an advisory prompt through frontend triggers refusal with educational links."""
    thread_id = api_create_thread(title="Advisory Test")
    try:
        query = "Should I invest in HDFC Mid-Cap Opportunities Fund?"
        res = api_send_message(query=query, thread_id=thread_id)

        assert res["is_refusal"] is True
        assert res["intent"] == "ADVISORY"
        assert "facts-only assistant" in res["answer"].lower()
        assert "https://www.amfiindia.com" in res["answer"]
        assert "https://investor.sebi.gov.in" in res["answer"]
    finally:
        api_delete_thread(thread_id)


def test_frontend_send_pii_message():
    """Verify PII in frontend query is detected and scrubbed."""
    thread_id = api_create_thread(title="PII Test")
    try:
        query = "My PAN is ABCDE1234F, what is the minimum SIP for HDFC Top 100?"
        res = api_send_message(query=query, thread_id=thread_id)

        assert "PAN" in res["detected_pii"]
        assert "ABCDE1234F" not in res["answer"]

        # History check
        history = api_get_messages(thread_id)
        assert len(history) == 2
        assert "ABCDE1234F" not in history[0]["content"]
        assert "[REDACTED_PAN]" in history[0]["content"]
    finally:
        api_delete_thread(thread_id)


def test_frontend_send_otp_message():
    """Verify OTP submission through frontend returns security notice."""
    thread_id = api_create_thread(title="OTP Test")
    try:
        query = "My OTP is 482910, confirm redemption"
        res = api_send_message(query=query, thread_id=thread_id)

        assert res["is_refusal"] is True
        assert res["intent"] == "SECURITY_ALERT"
        assert "Security Notice: Never share OTPs" in res["answer"]
    finally:
        api_delete_thread(thread_id)
