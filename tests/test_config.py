"""
Unit test for Phase 0 setup and configuration integrity.
"""

from src.config import (
    BASE_DIR,
    DATA_DIR,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    VECTOR_STORE_DIR,
    TARGET_AMC,
    TARGET_SCHEMES,
    EDUCATIONAL_LINKS,
    MANDATORY_DISCLAIMER,
    MAX_SENTENCES,
    EXACT_CITATION_COUNT,
    settings,
)


def test_directory_structure():
    """Verify all standard directories exist."""
    assert BASE_DIR.exists()
    assert DATA_DIR.exists()
    assert RAW_DATA_DIR.exists()
    assert PROCESSED_DATA_DIR.exists()
    assert VECTOR_STORE_DIR.exists()
    assert (BASE_DIR / "src" / "ingestion").exists()
    assert (BASE_DIR / "src" / "guardrails").exists()
    assert (BASE_DIR / "src" / "rag").exists()
    assert (BASE_DIR / "src" / "session").exists()
    assert (BASE_DIR / "src" / "api").exists()
    assert (BASE_DIR / "frontend").exists()
    assert (BASE_DIR / "tests").exists()


def test_scheme_roster_integrity():
    """Verify the 5 target schemes from problem statement are defined."""
    assert TARGET_AMC == "HDFC Mutual Fund"
    assert len(TARGET_SCHEMES) == 5

    expected_scheme_keys = [
        "hdfc-mid-cap-fund-direct-growth",
        "hdfc-small-cap-fund-direct-growth",
        "hdfc-large-cap-fund-direct-growth",
        "hdfc-silver-etf-fof-direct-growth",
        "hdfc-multi-cap-fund-direct-growth",
    ]

    for key in expected_scheme_keys:
        assert key in TARGET_SCHEMES
        scheme = TARGET_SCHEMES[key]
        assert scheme.source_url.startswith("https://groww.in/mutual-funds/")
        assert len(scheme.scheme_name) > 0
        assert len(scheme.category) > 0


def test_regulatory_and_disclaimer_settings():
    """Verify disclaimers, educational links, and generation constraints."""
    assert MANDATORY_DISCLAIMER == "Facts-only. No investment advice."
    assert "AMFI" in EDUCATIONAL_LINKS
    assert "SEBI_INVESTOR" in EDUCATIONAL_LINKS
    assert MAX_SENTENCES == 3
    assert EXACT_CITATION_COUNT == 1


def test_settings_initialization():
    """Verify runtime settings defaults."""
    assert settings.groq_model == "llama-3.3-70b-versatile"
    assert settings.embedding_model_name == "all-MiniLM-L6-v2"
    assert settings.groq_temperature == 0.0
