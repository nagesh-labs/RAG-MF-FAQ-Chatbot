"""
Comprehensive Unit Tests for Milestone RAG Core Pipeline & Synthesis.
Tests:
1. Retriever: Metadata-filtered vector search, multi-scheme retrieval, and operational guides.
2. Validator: Sentence trimming (<=3 sentences), single citation enforcement, and mandatory footer.
3. Generator: Prompt formatting, Groq client synthesis, extractive fallback, and full compliance.
"""

from unittest.mock import MagicMock, AsyncMock
import pytest
import re
from src.config import TARGET_SCHEMES
from src.rag.retriever import (
    RetrievedChunk,
    extract_all_scheme_entities,
    retrieve_context,
    get_canonical_citation_for_scheme,
)
from src.rag.validator import (
    tokenize_sentences,
    trim_to_max_sentences,
    extract_and_enforce_single_citation,
    format_and_validate_response,
    verify_compliance,
)
from src.rag.generator import (
    build_context_block,
    generate_answer,
    async_generate_answer,
    _extractive_fallback_synthesizer,
)


# =====================================================================
# 1. Retriever Unit Tests
# =====================================================================

def test_single_scheme_retrieval_mid_cap():
    """Verify metadata-filtered retrieval for HDFC Mid-Cap."""
    query = "What is the expense ratio for HDFC Mid-Cap Opportunities Fund Direct Growth?"
    chunks, scheme_id = retrieve_context(query, n_results=3)

    assert scheme_id == "hdfc-mid-cap-fund-direct-growth"
    assert len(chunks) > 0
    # All retrieved chunks should match the filtered scheme
    for chunk in chunks:
        assert chunk.scheme_id == "hdfc-mid-cap-fund-direct-growth"
    # Content check: expense ratio chunk should be retrieved
    texts = " ".join(c.text for c in chunks)
    assert "Expense Ratio" in texts or "expense" in texts.lower()


def test_single_scheme_retrieval_small_cap():
    """Verify exit load retrieval for HDFC Small Cap."""
    query = "What is the exit load for HDFC Small Cap Fund?"
    chunks, scheme_id = retrieve_context(query, n_results=3)

    assert scheme_id == "hdfc-small-cap-fund-direct-growth"
    assert len(chunks) > 0
    texts = " ".join(c.text for c in chunks)
    assert "Exit Load" in texts or "1.00%" in texts


def test_single_scheme_retrieval_large_cap():
    """Verify minimum SIP retrieval for HDFC Top 100 Large Cap."""
    query = "What is the minimum SIP amount for HDFC Top 100 Large Cap Fund?"
    chunks, scheme_id = retrieve_context(query, n_results=3)

    assert scheme_id == "hdfc-large-cap-fund-direct-growth"
    texts = " ".join(c.text for c in chunks)
    assert "Minimum Investment" in texts or "SIP" in texts


def test_single_scheme_retrieval_silver_etf():
    """Verify lock-in retrieval for HDFC Silver ETF FoF."""
    query = "What is the lock-in period for HDFC Silver ETF Fund of Fund?"
    chunks, scheme_id = retrieve_context(query, n_results=3)

    assert scheme_id == "hdfc-silver-etf-fof-direct-growth"
    texts = " ".join(c.text for c in chunks)
    assert "Lock-in" in texts or "lock" in texts.lower()


def test_single_scheme_retrieval_multi_cap():
    """Verify benchmark retrieval for HDFC Multi-Cap Fund."""
    query = "What is the benchmark index for HDFC Multi-Cap Fund?"
    chunks, scheme_id = retrieve_context(query, n_results=3)

    assert scheme_id == "hdfc-multi-cap-fund-direct-growth"
    texts = " ".join(c.text for c in chunks)
    assert "NIFTY 500" in texts or "Benchmark" in texts


def test_multi_scheme_retrieval():
    """Verify retrieval when two schemes are mentioned in a single prompt."""
    query = "Compare the exit load of HDFC Mid Cap and HDFC Small Cap"
    detected = extract_all_scheme_entities(query)
    assert "hdfc-mid-cap-fund-direct-growth" in detected
    assert "hdfc-small-cap-fund-direct-growth" in detected

    chunks, primary = retrieve_context(query, n_results=4)
    assert len(chunks) >= 2
    scheme_ids_retrieved = {c.scheme_id for c in chunks}
    assert "hdfc-mid-cap-fund-direct-growth" in scheme_ids_retrieved
    assert "hdfc-small-cap-fund-direct-growth" in scheme_ids_retrieved


def test_operational_guide_retrieval():
    """Verify operational guides (statement download, capital gains) are retrievable."""
    query = "How to download capital gains statement on Groww?"
    chunks, scheme_id = retrieve_context(query, n_results=3)

    assert len(chunks) > 0
    texts = " ".join(c.text for c in chunks)
    assert "Capital Gains" in texts or "Reports" in texts


def test_canonical_citation_resolution():
    """Verify canonical citation resolution for each scheme and default."""
    for scheme_id, scheme in TARGET_SCHEMES.items():
        name, url = get_canonical_citation_for_scheme(scheme_id)
        assert name == scheme.scheme_name
        assert url == scheme.source_url

    default_name, default_url = get_canonical_citation_for_scheme(None)
    assert default_name == "Groww Mutual Funds"
    assert "groww.in/mutual-funds" in default_url


# =====================================================================
# 2. Validator Unit Tests
# =====================================================================

def test_tokenize_sentences():
    """Verify sentence tokenization handles punctuation and abbreviations."""
    text = "The expense ratio is 0.70%. The exit load is 1.00% within 1 year. There is no lock-in period."
    sents = tokenize_sentences(text)
    assert len(sents) == 3


def test_sentence_trimmer_excess_sentences():
    """Verify that a response with > 3 sentences is trimmed to exactly 3."""
    long_text = (
        "Sentence one is about expense ratio. "
        "Sentence two is about exit load. "
        "Sentence three is about minimum SIP. "
        "Sentence four should be trimmed off. "
        "Sentence five should also be trimmed off."
    )
    trimmed = trim_to_max_sentences(long_text, max_sentences=3)
    sents = tokenize_sentences(trimmed)
    assert len(sents) == 3
    assert "Sentence four" not in trimmed
    assert "Sentence five" not in trimmed


def test_sentence_trimmer_short_sentences():
    """Verify that a response with <= 3 sentences is preserved completely."""
    short_text = "The minimum SIP is ₹100 per month. There is no upper limit."
    trimmed = trim_to_max_sentences(short_text, max_sentences=3)
    assert trimmed == short_text


def test_single_citation_appended_when_missing():
    """Verify citation link is appended when none is in raw response."""
    raw = "The exit load for HDFC Small Cap Fund is 1% if redeemed within 1 year."
    body, citation = extract_and_enforce_single_citation(
        raw,
        canonical_url="https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
        canonical_name="HDFC Small Cap Fund",
    )
    assert citation == "Source: [HDFC Small Cap Fund](https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth)"
    assert body == raw


def test_single_citation_preserves_existing():
    """Verify existing single citation is preserved."""
    raw = (
        "The minimum SIP is ₹100 per month.\n\n"
        "Source: [HDFC Mid-Cap Details](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth)"
    )
    body, citation = extract_and_enforce_single_citation(
        raw,
        canonical_url="https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    )
    assert citation == "Source: [HDFC Mid-Cap Details](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth)"
    assert "The minimum SIP is ₹100 per month." in body


def test_single_citation_strips_duplicate_links():
    """Verify multiple markdown links are reduced to exactly 1 link."""
    raw = (
        "Check [HDFC Small Cap](https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth) "
        "and [HDFC Mid Cap](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth) for details."
    )
    body, citation = extract_and_enforce_single_citation(
        raw,
        canonical_url="https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
    )
    # The output should have citation at the bottom and no active markdown link in the body
    assert citation.startswith("Source: [HDFC Small Cap]")
    assert "https://" not in body


def test_format_and_validate_response_full_compliance():
    """Verify end-to-end validator produces a fully compliant output."""
    raw = (
        "HDFC Mid-Cap Opportunities Fund Direct-Growth has an expense ratio of 0.70%. "
        "The minimum SIP investment is ₹100 per month. "
        "The exit load is 1% if redeemed within 1 year of allotment. "
        "This fourth sentence should be cleanly trimmed by the validator."
    )
    url = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
    name = "HDFC Mid-Cap Opportunities Fund"

    formatted = format_and_validate_response(
        raw_response=raw,
        canonical_url=url,
        canonical_name=name,
        date_str="2026-10-25",
    )

    # 1. Must end with footer
    assert formatted.endswith("*Last updated from sources: 2026-10-25*")
    # 2. Check sentence count <= 3
    compliance = verify_compliance(formatted)
    assert compliance["is_compliant"] is True
    assert compliance["sentence_count"] == 3
    assert compliance["exact_single_citation"] is True
    assert compliance["has_footer"] is True


# =====================================================================
# 3. Generator Unit Tests
# =====================================================================

def test_build_context_block():
    """Verify retrieved chunks are formatted into readable context block."""
    chunk = RetrievedChunk(
        chunk_id="test_1",
        text="Expense Ratio: 0.70%.",
        scheme_id="hdfc-mid-cap-fund-direct-growth",
        scheme_name="HDFC Mid-Cap Opportunities Fund",
        category="Mid Cap Equity",
        source_url="https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        attribute_type="expense_ratio",
        distance=0.1,
    )
    block = build_context_block([chunk])
    assert "HDFC Mid-Cap Opportunities Fund" in block
    assert "Expense Ratio: 0.70%." in block
    assert "Source URL:" in block


def test_extractive_fallback_synthesizer():
    """Verify extractive fallback produces fact-based output under 3 sentences."""
    chunk = RetrievedChunk(
        chunk_id="test_1",
        text=(
            "Scheme: HDFC Small Cap Fund. "
            "Exit Load: 1.00% if redeemed within 1 year. "
            "Nil exit load after 1 year. "
            "Units can be redeemed anytime."
        ),
        scheme_id="hdfc-small-cap-fund-direct-growth",
        scheme_name="HDFC Small Cap Fund",
        category="Small Cap Equity",
        source_url="https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
        attribute_type="exit_load",
        distance=0.05,
    )
    body = _extractive_fallback_synthesizer(
        query="What is the exit load?",
        chunks=[chunk],
        canonical_name="HDFC Small Cap Fund",
        canonical_url="https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
    )
    assert "Exit Load: 1.00%" in body
    sents = tokenize_sentences(body)
    assert len(sents) <= 3


def test_generate_answer_without_api_key():
    """Verify generate_answer runs smoothly with extractive fallback when API key is missing."""
    chunks, scheme_id = retrieve_context("What is the expense ratio of HDFC Mid-Cap Opportunities Fund?")
    answer = generate_answer(
        query="What is the expense ratio of HDFC Mid-Cap Opportunities Fund?",
        retrieved_chunks=chunks,
        primary_scheme_id=scheme_id,
    )
    assert "expense ratio" in answer.lower()
    compliance = verify_compliance(answer)
    assert compliance["is_compliant"] is True


def test_generate_answer_with_mocked_groq():
    """Verify Groq API client integration and prompt passing via mock."""
    mock_groq = MagicMock()
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = (
        "The minimum SIP amount for HDFC Mid-Cap Opportunities Fund Direct-Growth is ₹100 per month. "
        "There is no maximum investment limit for SIPs in this scheme.\n\n"
        "Source: [HDFC Mid-Cap Fund Details](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth)"
    )
    mock_choice.message = mock_message
    mock_completion.choices = [mock_choice]
    mock_groq.chat.completions.create.return_value = mock_completion

    chunks, scheme_id = retrieve_context("What is the minimum SIP for HDFC Mid Cap?")
    answer = generate_answer(
        query="What is the minimum SIP for HDFC Mid Cap?",
        retrieved_chunks=chunks,
        primary_scheme_id=scheme_id,
        client=mock_groq,
    )

    # Verify mock was called with correct parameters
    assert mock_groq.chat.completions.create.called
    call_kwargs = mock_groq.chat.completions.create.call_args.kwargs
    assert call_kwargs["temperature"] == 0.0
    assert len(call_kwargs["messages"]) == 2
    assert "₹100" in answer

    # Verify final compliance
    compliance = verify_compliance(answer)
    assert compliance["is_compliant"] is True


def test_async_generate_answer():
    """Verify async generation works seamlessly."""
    import asyncio
    chunks, scheme_id = retrieve_context("What is the benchmark of HDFC Multi-Cap Fund?")
    answer = asyncio.run(
        async_generate_answer(
            query="What is the benchmark of HDFC Multi-Cap Fund?",
            retrieved_chunks=chunks,
            primary_scheme_id=scheme_id,
        )
    )
    assert "nifty 500" in answer.lower() or "benchmark" in answer.lower()
    compliance = verify_compliance(answer)
    assert compliance["is_compliant"] is True

