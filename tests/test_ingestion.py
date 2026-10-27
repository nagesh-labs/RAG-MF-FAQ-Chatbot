"""
Unit tests for Phase 1 Data Ingestion and ChromaDB Indexing.
"""

import json
from pathlib import Path
import chromadb
import pytest

from src.config import PROCESSED_DATA_DIR, RAW_DATA_DIR, VECTOR_STORE_DIR, TARGET_SCHEMES, settings
from src.ingestion.embedder import query_corpus


def test_raw_snapshots_exist():
    """Verify raw HTML snapshots were fetched and saved in data/raw for all 5 schemes."""
    for scheme_id in TARGET_SCHEMES.keys():
        html_file = RAW_DATA_DIR / f"{scheme_id}.html"
        assert html_file.exists(), f"Raw snapshot missing for {scheme_id}"
        assert html_file.stat().st_size > 1000, f"Snapshot too small for {scheme_id}"


def test_normalized_json_documents():
    """Verify all 5 schemes and operational guides have structured JSON models in data/processed."""
    required_fields = [
        "scheme_id",
        "scheme_name",
        "category",
        "amc",
        "expense_ratio",
        "exit_load",
        "min_sip_amount",
        "min_lumpsum_amount",
        "lock_in_period",
        "riskometer",
        "benchmark_index",
        "fund_manager",
        "aum",
        "source_url",
    ]

    for scheme_id in TARGET_SCHEMES.keys():
        json_file = PROCESSED_DATA_DIR / f"{scheme_id}.json"
        assert json_file.exists(), f"Normalized clean JSON missing for {scheme_id} in data/processed"
        
        data = json.loads(json_file.read_text(encoding="utf-8"))
        for field in required_fields:
            assert field in data, f"Field '{field}' missing in {scheme_id}.json"
            assert data[field] is not None and len(str(data[field])) > 0

    guides_file = PROCESSED_DATA_DIR / "operational_guides.json"
    assert guides_file.exists(), "operational_guides.json missing in data/processed"
    guides = json.loads(guides_file.read_text(encoding="utf-8"))
    assert len(guides) >= 3


def test_chromadb_collection_count():
    """Verify ChromaDB holds the expected number of indexed chunks."""
    client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
    collection = client.get_collection(name=settings.chroma_collection_name)
    count = collection.count()
    assert count >= 43, f"Expected at least 43 chunks, found {count}"


def test_semantic_retrieval_precision():
    """Verify semantic retrieval returns the correct scheme document and metadata."""
    res = query_corpus("What is the exit load for HDFC Silver ETF?", n_results=1)
    documents = res["documents"][0]
    metadatas = res["metadatas"][0]

    assert len(documents) > 0
    assert "silver" in documents[0].lower()
    assert metadatas[0]["source_url"] == "https://groww.in/mutual-funds/hdfc-silver-etf-fof-direct-growth"
