"""
Central configuration module for the Milestone RAG Mutual Fund FAQ Assistant.
Defines scheme rosters, regulatory links, system constraints, and environment parameters.
"""

from pathlib import Path
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
VECTOR_STORE_DIR = DATA_DIR / "vector_store"
DOCS_DIR = BASE_DIR / "docs"

# Load environment variables
load_dotenv(BASE_DIR / ".env", override=True)


class SchemeMetadata(BaseModel):
    """Metadata schema for a verified target mutual fund scheme."""
    scheme_id: str
    scheme_name: str
    category: str
    source_url: str
    aliases: List[str] = Field(default_factory=list)


# Target Asset Management Company (AMC)
TARGET_AMC: str = "HDFC Mutual Fund"

# Whitelisted Schemes Corpus
TARGET_SCHEMES: Dict[str, SchemeMetadata] = {
    "hdfc-mid-cap-fund-direct-growth": SchemeMetadata(
        scheme_id="hdfc-mid-cap-fund-direct-growth",
        scheme_name="HDFC Mid-Cap Opportunities Fund Direct-Growth",
        category="Mid Cap Equity",
        source_url="https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        aliases=["hdfc mid cap", "hdfc midcap", "mid cap opportunities", "hdfc mid cap fund"],
    ),
    "hdfc-small-cap-fund-direct-growth": SchemeMetadata(
        scheme_id="hdfc-small-cap-fund-direct-growth",
        scheme_name="HDFC Small Cap Fund Direct-Growth",
        category="Small Cap Equity",
        source_url="https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
        aliases=["hdfc small cap", "hdfc smallcap", "small cap fund", "hdfc small cap fund"],
    ),
    "hdfc-large-cap-fund-direct-growth": SchemeMetadata(
        scheme_id="hdfc-large-cap-fund-direct-growth",
        scheme_name="HDFC Large Cap Fund Direct-Growth",
        category="Large Cap Equity",
        source_url="https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
        aliases=["hdfc large cap", "hdfc top 100", "top 100 fund", "hdfc large cap fund", "hdfc top 100 fund"],
    ),
    "hdfc-silver-etf-fof-direct-growth": SchemeMetadata(
        scheme_id="hdfc-silver-etf-fof-direct-growth",
        scheme_name="HDFC Silver ETF Fund of Fund Direct-Growth",
        category="Commodities / Silver FoF",
        source_url="https://groww.in/mutual-funds/hdfc-silver-etf-fof-direct-growth",
        aliases=["hdfc silver etf", "silver fof", "silver etf fof", "hdfc silver fund"],
    ),
    "hdfc-multi-cap-fund-direct-growth": SchemeMetadata(
        scheme_id="hdfc-multi-cap-fund-direct-growth",
        scheme_name="HDFC Multi-Cap Fund Direct-Growth",
        category="Multi Cap Equity",
        source_url="https://groww.in/mutual-funds/hdfc-multi-cap-fund-direct-growth",
        aliases=["hdfc multi cap", "hdfc multicap", "multi cap fund", "hdfc multi cap fund"],
    ),
}

# Educational & Regulatory Resources
EDUCATIONAL_LINKS: Dict[str, str] = {
    "AMFI": "https://www.amfiindia.com",
    "SEBI_INVESTOR": "https://investor.sebi.gov.in",
    "GROWW_MF": "https://groww.in/mutual-funds",
}

# Mandatory System Disclaimers & Footers
MANDATORY_DISCLAIMER: str = "Facts-only. No investment advice."
FOOTER_TEMPLATE: str = "Last updated from sources: {date}"

# Formatting & Generation Constraints
MAX_SENTENCES: int = 3
EXACT_CITATION_COUNT: int = 1

# Quick Starter Questions for UI
STARTER_QUESTIONS: List[str] = [
    "What is the exit load for HDFC Small Cap Fund?",
    "What is the minimum SIP amount for HDFC Mid-Cap Fund?",
    "What is the benchmark index for HDFC Multi-Cap Fund?",
]

# Standard Refusal Message Template
STANDARD_REFUSAL_MESSAGE: str = (
    "I am a facts-only assistant and cannot provide investment advice, scheme recommendations, "
    "or opinions on which fund is better. For investment guidance, please consult a SEBI-registered "
    "advisor or explore educational resources on [AMFI India](https://www.amfiindia.com) "
    "and [SEBI Investor Education](https://investor.sebi.gov.in)."
)


class Settings(BaseModel):
    """Runtime application settings with environment variable fallback."""
    # Groq LLM Settings
    groq_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_model: str = Field(default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
    groq_temperature: float = 0.0  # Zero temperature for deterministic factual extraction
    groq_max_tokens: int = 512

    # Embedding & Vector Database Settings
    embedding_model_name: str = Field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    )
    vector_store_path: Path = Field(
        default_factory=lambda: Path(os.getenv("VECTOR_STORE_PATH", str(VECTOR_STORE_DIR)))
    )
    chroma_collection_name: str = "hdfc_mutual_funds"

    # SQLite Database for Multi-Thread Session Storage
    database_path: Path = Field(
        default_factory=lambda: Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "threads.db")))
    )

    # Server Settings
    api_host: str = Field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    api_port: int = Field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    frontend_port: int = Field(
        default_factory=lambda: int(os.getenv("FRONTEND_PORT", os.getenv("PORT", "8501")))
    )


# Global settings singleton
settings = Settings()
