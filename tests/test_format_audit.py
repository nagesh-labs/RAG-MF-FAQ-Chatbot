"""
Task 7.3: Format & Constraint Automated Audit Suite.
Scripted audit of 50 responses validating:
1. Sentence count <= 3
2. Exactly 1 citation URL
3. Timestamp footer matches format (*Last updated from sources: YYYY-MM-DD*)
"""

import re
import pytest
from src.rag.retriever import retrieve_context
from src.rag.generator import generate_answer
from src.rag.validator import tokenize_sentences, extract_and_enforce_single_citation


# 50 diverse factual queries
AUDIT_QUERIES = [
    # HDFC Mid-Cap (10 queries)
    "What is the expense ratio for HDFC Mid-Cap Opportunities Fund?",
    "What is the exit load for HDFC Mid Cap?",
    "What is the minimum SIP for HDFC Mid-Cap Opportunities Fund?",
    "What is the minimum lumpsum investment in HDFC Mid-Cap?",
    "What is the lock-in period for HDFC Mid-Cap Fund?",
    "What is the riskometer rating of HDFC Mid Cap Opportunities?",
    "What is the benchmark index of HDFC Mid-Cap?",
    "Who is the fund manager of HDFC Mid-Cap Opportunities Fund?",
    "What is the total AUM of HDFC Mid Cap Fund?",
    "What is the category of HDFC Mid-Cap Opportunities Fund?",

    # HDFC Small Cap (10 queries)
    "What is the expense ratio for HDFC Small Cap Fund Direct Growth?",
    "What is the exit load for HDFC Small Cap Fund?",
    "What is the minimum SIP amount in HDFC Small Cap?",
    "What is the minimum lumpsum for HDFC Small Cap Fund?",
    "Does HDFC Small Cap Fund have any lock-in period?",
    "What is the riskometer score for HDFC Small Cap?",
    "What is the benchmark index for HDFC Small Cap Fund?",
    "Who manages HDFC Small Cap Fund?",
    "What is the AUM for HDFC Small Cap Fund?",
    "What is the asset category of HDFC Small Cap?",

    # HDFC Large Cap / Top 100 (10 queries)
    "What is the expense ratio of HDFC Top 100 Fund Large Cap?",
    "What is the exit load of HDFC Top 100 Large Cap Fund?",
    "What is the minimum SIP for HDFC Large Cap Fund?",
    "What is the minimum lumpsum for HDFC Top 100?",
    "Is there a lock-in period for HDFC Top 100 Large Cap Fund?",
    "What is the riskometer for HDFC Large Cap Fund?",
    "What benchmark does HDFC Top 100 track?",
    "Who is the fund manager of HDFC Large Cap Fund?",
    "What is the AUM of HDFC Top 100 Fund?",
    "Tell me the category of HDFC Top 100 Fund.",

    # HDFC Silver ETF FoF (10 queries)
    "What is the expense ratio of HDFC Silver ETF Fund of Fund?",
    "What is the exit load for HDFC Silver ETF FoF?",
    "What is the minimum SIP in HDFC Silver ETF Fund of Fund?",
    "What is the minimum lumpsum for HDFC Silver ETF FoF?",
    "What is the lock in period for HDFC Silver ETF Fund of Fund?",
    "What is the riskometer rating for HDFC Silver ETF FoF?",
    "What is the benchmark for HDFC Silver ETF FoF?",
    "Who is the fund manager of HDFC Silver ETF FoF?",
    "What is the AUM of HDFC Silver ETF Fund of Fund?",
    "What category does HDFC Silver ETF FoF belong to?",

    # HDFC Multi-Cap & Operational Guides (10 queries)
    "What is the expense ratio for HDFC Multi-Cap Fund?",
    "What is the exit load for HDFC Multi Cap Fund?",
    "What is the minimum SIP for HDFC Multi-Cap Fund?",
    "What is the minimum lumpsum for HDFC Multi-Cap Fund?",
    "Does HDFC Multi-Cap Fund have a lock-in period?",
    "What is the benchmark index for HDFC Multi-Cap Fund?",
    "Who manages HDFC Multi-Cap Fund?",
    "How do I download my mutual fund account statement?",
    "Where to download capital gains report on Groww?",
    "What is the ELSS lock-in rule compared to HDFC equity funds?"
]


@pytest.mark.parametrize("query", AUDIT_QUERIES)
def test_response_sentence_count_ceiling(query):
    """Verify narrative body has at most 3 sentences."""
    chunks, scheme_id = retrieve_context(query)
    answer = generate_answer(query, chunks, primary_scheme_id=scheme_id)

    # Exclude Source line and timestamp footer before counting sentences
    body = answer.split("Source:")[0].split("*Last updated from sources:")[0].strip()
    sentences = tokenize_sentences(body)
    assert len(sentences) <= 3, f"Sentence count {len(sentences)} exceeded ceiling 3 for query: '{query}'"


@pytest.mark.parametrize("query", AUDIT_QUERIES)
def test_response_exact_single_citation(query):
    """Verify response contains exactly one source citation URL."""
    chunks, scheme_id = retrieve_context(query)
    answer = generate_answer(query, chunks, primary_scheme_id=scheme_id)

    links = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', answer)
    assert len(links) == 1, f"Expected exactly 1 citation link, found {len(links)} in answer:\n{answer}"
    assert "groww.in" in links[0][1], f"Citation link must point to Groww source: {links[0][1]}"


@pytest.mark.parametrize("query", AUDIT_QUERIES)
def test_response_mandatory_timestamp_footer(query):
    """Verify response ends with mandatory Last updated from sources footer."""
    chunks, scheme_id = retrieve_context(query)
    answer = generate_answer(query, chunks, primary_scheme_id=scheme_id)

    footer_match = re.search(r'Last updated from sources:\s*\d{4}-\d{2}-\d{2}', answer)
    assert footer_match is not None, f"Missing or malformed timestamp footer in answer:\n{answer}"
