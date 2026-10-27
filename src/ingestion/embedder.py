"""
Embedding and Vector Store Manager for Milestone RAG.
Transforms normalized scheme JSONs and operational guides into atomic semantic chunks,
generates dense vector embeddings via sentence-transformers, and indexes them in ChromaDB.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import chromadb
from sentence_transformers import SentenceTransformer

import sys
from src.config import PROCESSED_DATA_DIR, RAW_DATA_DIR, VECTOR_STORE_DIR, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)


class SemanticChunk:
    """Represents a text chunk tagged with rich metadata for retrieval."""
    def __init__(self, chunk_id: str, text: str, metadata: Dict[str, Any]):
        self.chunk_id = chunk_id
        self.text = text
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.chunk_id,
            "text": self.text,
            "metadata": self.metadata,
        }


def create_scheme_chunks(scheme_data: Dict[str, Any]) -> List[SemanticChunk]:
    """
    Generate atomic, field-level semantic chunks for a single scheme.
    
    Args:
        scheme_data: Dictionary loaded from normalized scheme JSON.
        
    Returns:
        List of SemanticChunk objects.
    """
    scheme_id = scheme_data["scheme_id"]
    scheme_name = scheme_data["scheme_name"]
    category = scheme_data["category"]
    source_url = scheme_data["source_url"]
    date_str = scheme_data.get("last_updated_date", "2026-10-25")
    base_meta = {
        "scheme_id": scheme_id,
        "scheme_name": scheme_name,
        "category": category,
        "source_url": source_url,
        "last_updated_date": date_str,
    }

    ret_lump = scheme_data.get("returns_lumpsum", {})
    ret_sip = scheme_data.get("returns_sip", {})
    holdings_list = scheme_data.get("top_holdings", [])
    holdings_str = ", ".join([f"{h['company_name']} ({h['corpus_percent']})" for h in holdings_list]) if holdings_list else "Physical commodities / FoF underlying assets"
    ratios = scheme_data.get("risk_ratios", {})

    chunks = [
        # 1. Expense Ratio Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_expense_ratio",
            text=(
                f"Scheme: {scheme_name} ({category}). "
                f"Expense Ratio: The expense ratio is {scheme_data['expense_ratio']}. "
                f"Direct plans have a lower expense ratio compared to regular plans."
            ),
            metadata={**base_meta, "attribute_type": "expense_ratio"},
        ),
        # 2. Exit Load Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_exit_load",
            text=(
                f"Scheme: {scheme_name} ({category}). "
                f"Exit Load Details: {scheme_data['exit_load']} "
                f"Exit load is charged as a percentage of the redemption value if redeemed within the specified period."
            ),
            metadata={**base_meta, "attribute_type": "exit_load"},
        ),
        # 3. Minimum SIP & Investment Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_min_investment",
            text=(
                f"Scheme: {scheme_name} ({category}). "
                f"Minimum Investment Limits: Minimum SIP amount is {scheme_data['min_sip_amount']} per month. "
                f"Minimum Lump sum (one-time) investment amount is {scheme_data['min_lumpsum_amount']}."
            ),
            metadata={**base_meta, "attribute_type": "min_investment"},
        ),
        # 4. Lock-in Period Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_lock_in",
            text=(
                f"Scheme: {scheme_name} ({category}). "
                f"Lock-in Period: {scheme_data['lock_in_period']}. "
                f"Investors can redeem their units at any time subject to applicable exit loads."
            ),
            metadata={**base_meta, "attribute_type": "lock_in"},
        ),
        # 5. Riskometer Classification Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_riskometer",
            text=(
                f"Scheme: {scheme_name} ({category}). "
                f"Riskometer Rating: Classified under {scheme_data['riskometer']}. "
                f"Investors understand that their principal will be at high or very high risk."
            ),
            metadata={**base_meta, "attribute_type": "riskometer"},
        ),
        # 6. Benchmark Index Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_benchmark",
            text=(
                f"Scheme: {scheme_name} ({category}). "
                f"Benchmark Index: The scheme's benchmark is {scheme_data['benchmark_index']}. "
                f"Fund performance is evaluated against this Total Return Index (TRI)."
            ),
            metadata={**base_meta, "attribute_type": "benchmark"},
        ),
        # 7. Fund Manager & AUM Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_fund_manager_aum",
            text=(
                f"Scheme: {scheme_name} ({category}). "
                f"Fund Management and AUM: Managed by {scheme_data.get('fund_manager', 'HDFC AMC')}. "
                f"Total Assets Under Management (AUM) is {scheme_data.get('aum', 'refer to monthly factsheet')}."
            ),
            metadata={**base_meta, "attribute_type": "fund_manager_aum"},
        ),
        # 8. NAV and NAV Date Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_nav",
            text=(
                f"Scheme: {scheme_name} ({category}). "
                f"Net Asset Value (NAV): The latest Net Asset Value (NAV) is {scheme_data.get('nav', 'N/A')} "
                f"as of {scheme_data.get('nav_date', 'latest disclosure')}. "
                f"Mutual fund NAVs are declared at the end of each business day based on closing market prices."
            ),
            metadata={**base_meta, "attribute_type": "nav"},
        ),
        # 9. Fund Rating Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_rating",
            text=(
                f"Scheme: {scheme_name} ({category}). "
                f"Fund Rating: The scheme is rated {scheme_data.get('groww_rating', 'Not Rated')} on Groww. "
                f"Ratings are quantitative assessments based on historical risk-adjusted performance."
            ),
            metadata={**base_meta, "attribute_type": "rating"},
        ),
        # 10. Historical Lumpsum Returns Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_returns_lumpsum",
            text=(
                f"Scheme: {scheme_name} ({category}). "
                f"Historical Lumpsum Returns: 1-Year Return: {ret_lump.get('1Y', 'N/A')}, "
                f"3-Year Annualized Return: {ret_lump.get('3Y', 'N/A')}, "
                f"5-Year Annualized Return: {ret_lump.get('5Y', 'N/A')}, "
                f"10-Year Annualized Return: {ret_lump.get('10Y', 'N/A')}, "
                f"Return Since Inception: {ret_lump.get('since_inception', 'N/A')}. "
                f"Past performance is factual historical data and does not indicate future returns."
            ),
            metadata={**base_meta, "attribute_type": "returns_lumpsum"},
        ),
        # 11. Historical SIP Returns Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_returns_sip",
            text=(
                f"Scheme: {scheme_name} ({category}). "
                f"Historical SIP Returns (XIRR): 1-Year SIP: {ret_sip.get('1Y', 'N/A')}, "
                f"3-Year SIP: {ret_sip.get('3Y', 'N/A')}, "
                f"5-Year SIP: {ret_sip.get('5Y', 'N/A')}, "
                f"10-Year SIP: {ret_sip.get('10Y', 'N/A')}, "
                f"SIP Return Since Inception: {ret_sip.get('since_inception', 'N/A')}. "
                f"Past SIP performance is factual historical data and does not guarantee future results."
            ),
            metadata={**base_meta, "attribute_type": "returns_sip"},
        ),
        # 12. Top Portfolio Holdings Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_holdings",
            text=(
                f"Scheme: {scheme_name} ({category}). "
                f"Top Portfolio Holdings: {holdings_str}. "
                f"Holdings represent the top portfolio allocations according to the latest factsheet."
            ),
            metadata={**base_meta, "attribute_type": "holdings"},
        ),
        # 13. Portfolio Turnover, Launch Date, Stamp Duty Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_turnover_launch",
            text=(
                f"Scheme: {scheme_name} ({category}). "
                f"Portfolio Turnover Ratio: {scheme_data.get('portfolio_turnover', 'N/A')}. "
                f"Inception / Launch Date: {scheme_data.get('launch_date', 'N/A')}. "
                f"Stamp Duty: {scheme_data.get('stamp_duty', '0.005%')} is levied on mutual fund purchases."
            ),
            metadata={**base_meta, "attribute_type": "turnover_launch"},
        ),
        # 14. Risk & Volatility Ratios Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_risk_ratios",
            text=(
                f"Scheme: {scheme_name} ({category}). "
                f"Historical Risk & Volatility Ratios: Standard Deviation: {ratios.get('standard_deviation', 'N/A')}, "
                f"Beta: {ratios.get('beta', 'N/A')}, Sharpe Ratio: {ratios.get('sharpe_ratio', 'N/A')}, "
                f"Sortino Ratio: {ratios.get('sortino_ratio', 'N/A')}, Alpha: {ratios.get('alpha', 'N/A')}. "
                f"These metrics represent historical mathematical volatility relative to the benchmark."
            ),
            metadata={**base_meta, "attribute_type": "risk_ratios"},
        ),
        # 15. Comprehensive Scheme Summary Chunk
        SemanticChunk(
            chunk_id=f"{scheme_id}_summary",
            text=(
                f"HDFC Mutual Fund Scheme: {scheme_name}. Category: {category}. "
                f"NAV: {scheme_data.get('nav', 'N/A')} (as of {scheme_data.get('nav_date', 'latest')}). "
                f"Rating: {scheme_data.get('groww_rating', 'N/A')}. "
                f"Expense Ratio: {scheme_data['expense_ratio']}. Exit Load: {scheme_data['exit_load']}. "
                f"Min SIP: {scheme_data['min_sip_amount']}, Min Lumpsum: {scheme_data['min_lumpsum_amount']}. "
                f"Benchmark: {scheme_data['benchmark_index']}. Riskometer: {scheme_data['riskometer']}. "
                f"Lock-in: {scheme_data['lock_in_period']}. AUM: {scheme_data.get('aum', 'N/A')}. "
                f"Managed by: {scheme_data['fund_manager']}. Launched: {scheme_data.get('launch_date', 'N/A')}."
            ),
            metadata={**base_meta, "attribute_type": "overview"},
        ),
    ]

    return chunks


def create_operational_chunks(guides_data: List[Dict[str, Any]]) -> List[SemanticChunk]:
    """
    Generate semantic chunks for operational guides (statements, capital gains, ELSS rules).
    """
    chunks = []
    for guide in guides_data:
        chunk = SemanticChunk(
            chunk_id=guide["guide_id"],
            text=f"Operational Process: {guide['title']}. Details: {guide['content']}",
            metadata={
                "scheme_id": "all",
                "scheme_name": "Mutual Fund Operational Guide",
                "category": guide.get("category", "Operational Guide"),
                "attribute_type": guide["guide_id"],
                "source_url": guide["source_url"],
                "last_updated_date": guide.get("last_updated_date", "2026-10-25"),
            },
        )
        chunks.append(chunk)
    return chunks


def build_and_index_corpus() -> int:
    """
    Loads all normalized JSON files, creates embeddings, and indexes them into ChromaDB.
    
    Returns:
        Total number of indexed chunks.
    """
    all_chunks: List[SemanticChunk] = []

    # 1. Process 5 Scheme JSONs from clean/processed data directory
    for json_file in PROCESSED_DATA_DIR.glob("hdfc-*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            chunks = create_scheme_chunks(data)
            all_chunks.extend(chunks)
            logger.info(f"Generated {len(chunks)} chunks for {data['scheme_id']}")
        except Exception as e:
            logger.error(f"Error loading {json_file.name}: {e}")

    # 2. Process Operational Guides from clean/processed data directory
    guides_file = PROCESSED_DATA_DIR / "operational_guides.json"
    if guides_file.exists():
        guides_data = json.loads(guides_file.read_text(encoding="utf-8"))
        op_chunks = create_operational_chunks(guides_data)
        all_chunks.extend(op_chunks)
        logger.info(f"Generated {len(op_chunks)} operational guide chunks.")

    if not all_chunks:
        logger.error("No chunks generated. Make sure normalized JSONs exist in data/processed/.")
        return 0

    # 3. Initialize Embedding Model & ChromaDB
    logger.info(f"Loading embedding model: {settings.embedding_model_name}")
    embedder = SentenceTransformer(settings.embedding_model_name)

    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
    
    # Reset/recreate collection for idempotent indexing
    try:
        chroma_client.delete_collection(name=settings.chroma_collection_name)
    except Exception:
        pass

    collection = chroma_client.create_collection(
        name=settings.chroma_collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    # 4. Compute Dense Vector Embeddings
    ids = [c.chunk_id for c in all_chunks]
    documents = [c.text for c in all_chunks]
    metadatas = [c.metadata for c in all_chunks]

    logger.info(f"Computing embeddings for {len(documents)} chunks...")
    embeddings = embedder.encode(documents, show_progress_bar=False, normalize_embeddings=True)

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings.tolist(),
    )

    logger.info(f"Successfully indexed {len(ids)} chunks in ChromaDB collection '{settings.chroma_collection_name}'.")
    return len(ids)


# Global cached singletons for low-latency inference
_embedder_cache: Optional[SentenceTransformer] = None
_chroma_collection_cache: Optional[Any] = None


def get_embedder() -> SentenceTransformer:
    """Lazy singleton loader for the sentence-transformers model."""
    global _embedder_cache
    if _embedder_cache is None:
        logger.info(f"Loading embedding model into memory: {settings.embedding_model_name}")
        _embedder_cache = SentenceTransformer(settings.embedding_model_name)
    return _embedder_cache


def get_chroma_collection():
    """Lazy singleton loader for the ChromaDB persistent collection."""
    global _chroma_collection_cache
    if _chroma_collection_cache is None:
        chroma_client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
        _chroma_collection_cache = chroma_client.get_collection(name=settings.chroma_collection_name)
    return _chroma_collection_cache


def query_corpus(
    query_text: str,
    scheme_id: Optional[str] = None,
    n_results: int = 3,
) -> Dict[str, Any]:
    """
    Retrieve top-k relevant chunks from ChromaDB with optional scheme_id filtering.
    
    Args:
        query_text: Search query.
        scheme_id: Optional scheme_id filter.
        n_results: Number of results to retrieve.
        
    Returns:
        ChromaDB query results dictionary.
    """
    collection = get_chroma_collection()
    embedder = get_embedder()

    query_embedding = embedder.encode([query_text], normalize_embeddings=True).tolist()
    where_filter = {"scheme_id": scheme_id} if scheme_id else None

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results,
        where=where_filter,
    )
    return results


if __name__ == "__main__":
    count = build_and_index_corpus()
    print(f"Indexing complete! Total chunks indexed: {count}")
