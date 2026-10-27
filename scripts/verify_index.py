"""
Verification script to validate ChromaDB indexing and retrieval for all 5 HDFC schemes.
Checks that all factual parameters and operational guides are queryable with verified metadata.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingestion.embedder import query_corpus
from src.config import TARGET_SCHEMES


def test_scheme_retrievals():
    test_queries = [
        {
            "title": "HDFC Small Cap Exit Load",
            "query": "What is the exit load for HDFC Small Cap Fund?",
            "expected_terms": ["1%", "1 year", "small cap"],
            "scheme_id": "hdfc-small-cap-fund-direct-growth",
        },
        {
            "title": "HDFC Mid-Cap Minimum SIP",
            "query": "What is the minimum SIP amount for HDFC Mid-Cap Opportunities Fund?",
            "expected_terms": ["100", "sip", "mid-cap"],
            "scheme_id": "hdfc-mid-cap-fund-direct-growth",
        },
        {
            "title": "HDFC Large Cap Expense Ratio",
            "query": "What is the expense ratio for HDFC Large Cap Fund?",
            "expected_terms": ["expense ratio", "direct plan"],
            "scheme_id": "hdfc-large-cap-fund-direct-growth",
        },
        {
            "title": "HDFC Large Cap NAV",
            "query": "What is the current NAV of HDFC Top 100 Fund?",
            "expected_terms": ["nav", "1,133", "2026"],
            "scheme_id": "hdfc-large-cap-fund-direct-growth",
        },
        {
            "title": "HDFC Mid-Cap Rating",
            "query": "What is the fund rating for HDFC Mid-Cap Opportunities Fund?",
            "expected_terms": ["rating", "4", "stars"],
            "scheme_id": "hdfc-mid-cap-fund-direct-growth",
        },
        {
            "title": "HDFC Small Cap Returns",
            "query": "What are the historical returns of HDFC Small Cap Fund?",
            "expected_terms": ["return", "%"],
            "scheme_id": "hdfc-small-cap-fund-direct-growth",
        },
        {
            "title": "HDFC Large Cap Top Holdings",
            "query": "What are the top holdings of HDFC Large Cap Fund?",
            "expected_terms": ["icici", "hdfc bank", "holding"],
            "scheme_id": "hdfc-large-cap-fund-direct-growth",
        },
        {
            "title": "HDFC Mid-Cap Turnover",
            "query": "What is the portfolio turnover of HDFC Mid-Cap Fund?",
            "expected_terms": ["turnover", "13%"],
            "scheme_id": "hdfc-mid-cap-fund-direct-growth",
        },
        {
            "title": "HDFC Silver ETF FoF Exit Load",
            "query": "What is the exit load for HDFC Silver ETF Fund of Fund?",
            "expected_terms": ["15 days", "silver"],
            "scheme_id": "hdfc-silver-fof-direct-growth" if "hdfc-silver-fof-direct-growth" in TARGET_SCHEMES else "hdfc-silver-etf-fof-direct-growth",
        },
        {
            "title": "HDFC Multi-Cap Benchmark Index",
            "query": "What is the benchmark index for HDFC Multi-Cap Fund?",
            "expected_terms": ["500", "multicap", "benchmark"],
            "scheme_id": "hdfc-multi-cap-fund-direct-growth",
        },
        {
            "title": "Operational: Download Statement",
            "query": "How do I download my mutual fund account statement?",
            "expected_terms": ["download", "statement", "reports"],
            "scheme_id": None,
        },
    ]

    print("=" * 80)
    print("VERIFYING CHROMADB CORPUS RETRIEVAL ACROSS ALL TARGET SCHEMES")
    print("=" * 80)

    all_passed = True

    for item in test_queries:
        title = item["title"]
        query = item["query"]
        expected = item["expected_terms"]
        scheme_id = item["scheme_id"]

        results = query_corpus(query_text=query, scheme_id=scheme_id, n_results=1)

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        if not documents:
            print(f"[FAIL] {title}: No document retrieved!")
            all_passed = False
            continue

        doc_text = documents[0].lower()
        meta = metadatas[0] if metadatas else {}

        # Check expected terms
        matched = [term for term in expected if term.lower() in doc_text]
        source_url = meta.get("source_url", "")
        has_url = source_url.startswith("https://")

        passed = len(matched) >= 1 and has_url

        if passed:
            print(f"[PASS] {title}")
            print(f"       Retrieved: {documents[0][:90]}...")
            print(f"       Source URL: {source_url}")
        else:
            print(f"[FAIL] {title}")
            print(f"       Doc: {doc_text}")
            print(f"       Matched terms: {matched} / Expected: {expected}")
            all_passed = False

    print("=" * 80)
    if all_passed:
        print("RESULT: ALL 5 SCHEMES AND OPERATIONAL GUIDES RETRIEVE SUCCESSFULLY!")
        return 0
    else:
        print("RESULT: SOME RETRIEVAL CHECKS FAILED.")
        return 1


if __name__ == "__main__":
    exit_code = test_scheme_retrievals()
    sys.exit(exit_code)
