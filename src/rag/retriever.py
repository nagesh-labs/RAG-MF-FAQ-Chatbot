"""
Hybrid Scheme Retriever for Milestone RAG.
Performs entity detection to resolve target HDFC schemes, applies metadata-filtered
vector search over ChromaDB, and gracefully falls back to corpus-wide search.
"""

from dataclasses import dataclass
import logging
import re
from typing import Dict, List, Optional, Tuple, Any

from src.config import TARGET_SCHEMES, SchemeMetadata
from src.guardrails.intent_router import extract_scheme_entity
from src.ingestion.embedder import query_corpus

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """Structured container for a retrieved semantic chunk."""
    chunk_id: str
    text: str
    scheme_id: str
    scheme_name: str
    category: str
    source_url: str
    attribute_type: str
    distance: float


def extract_all_scheme_entities(query: str) -> List[str]:
    """
    Detect all target scheme entities present in a query (e.g. for multi-entity comparison).
    
    Args:
        query: Inbound user query.
        
    Returns:
        List of canonical scheme_ids mentioned in the query.
    """
    q_lower = query.lower()
    q_norm = re.sub(r"[-_]", " ", q_lower)
    detected: List[str] = []

    for scheme_id, scheme in TARGET_SCHEMES.items():
        matched = False
        # Check canonical scheme name
        if scheme.scheme_name.lower() in q_lower or scheme.scheme_name.lower().replace("-", " ") in q_norm:
            matched = True
        else:
            # Check aliases
            for alias in scheme.aliases:
                alias_lower = alias.lower()
                if re.search(r"\b" + re.escape(alias_lower) + r"\b", q_lower) or re.search(
                    r"\b" + re.escape(alias_lower.replace("-", " ")) + r"\b", q_norm
                ):
                    matched = True
                    break

        if matched and scheme_id not in detected:
            detected.append(scheme_id)

    # Secondary heuristic for schemes if not explicitly matched above
    if not detected:
        primary = extract_scheme_entity(query)
        if primary:
            detected.append(primary)

    return detected


def _rerank_chunks(query: str, chunks: List[RetrievedChunk], top_k: int) -> List[RetrievedChunk]:
    """
    Rerank retrieved chunks by combining dense vector distance with attribute-level keyword relevance.
    Guarantees that exact attribute chunks (e.g. nav, returns, ratings, holdings) take precedence.
    """
    q_lower = query.lower()

    attr_keywords = {
        "nav": ["nav", "net asset value"],
        "rating": ["rating", "star", "rated", "groww rating"],
        "returns_sip": ["sip return", "sip returns", "xirr"],
        "returns_lumpsum": ["return", "returns", "cagr", "annualized return", "past performance"],
        "holdings": ["holding", "holdings", "portfolio", "stocks", "top companies", "company", "hold"],
        "turnover_launch": ["turnover", "launch", "inception", "stamp duty", "started", "launched"],
        "risk_ratios": ["standard deviation", "beta", "sharpe", "sortino", "alpha", "volatility"],
        "expense_ratio": ["expense ratio", "ter", "total expense ratio"],
        "exit_load": ["exit load", "redemption load", "penalty"],
        "min_investment": ["minimum sip", "min sip", "minimum investment", "lumpsum amount", "lump sum"],
        "lock_in": ["lock in", "lock-in", "locking period"],
        "riskometer": ["riskometer", "risk rating", "risk classification"],
        "benchmark": ["benchmark", "index", "tri"],
        "fund_manager_aum": ["fund manager", "managed by", "manager", "aum", "fund size"],
    }

    scored_chunks = []
    for c in chunks:
        # Base score from cosine distance (lower distance = higher base score)
        score = 1.0 - c.distance

        # Check if attribute_type matches query intent
        if c.attribute_type in attr_keywords:
            for kw in attr_keywords[c.attribute_type]:
                if kw in q_lower:
                    score += 0.35
                    break

        scored_chunks.append((score, c))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored_chunks[:top_k]]


def retrieve_context(
    query: str,
    n_results: int = 5,
) -> Tuple[List[RetrievedChunk], Optional[str]]:
    """
    Retrieve top-k relevant chunks from ChromaDB.
    Uses metadata filtering when a specific target scheme is identified.
    Falls back to corpus-wide search if no specific scheme is detected.
    Supports multi-scheme retrieval if multiple schemes are explicitly mentioned.
    Applies attribute-aware reranking to prioritize exact parameter matches.
    
    Args:
        query: User search query.
        n_results: Maximum number of chunks to return.
        
    Returns:
        Tuple of (list of RetrievedChunk, primary scheme_id or None).
    """
    detected_schemes = extract_all_scheme_entities(query)
    chunks: List[RetrievedChunk] = []

    if len(detected_schemes) == 1:
        # Single scheme detected: targeted metadata-filtered retrieval
        scheme_id = detected_schemes[0]
        # Query up to 12 candidate chunks from the scheme to ensure attribute coverage
        raw_results = query_corpus(query_text=query, scheme_id=scheme_id, n_results=max(n_results * 2, 12))
        parsed = _parse_chroma_results(raw_results)
        chunks = _rerank_chunks(query, parsed, top_k=n_results)
        primary_scheme_id = scheme_id

    elif len(detected_schemes) > 1:
        # Multi-scheme detected (e.g. compare two schemes): retrieve top chunks for each
        per_scheme_k = max(2, n_results // len(detected_schemes))
        for s_id in detected_schemes:
            s_results = query_corpus(query_text=query, scheme_id=s_id, n_results=per_scheme_k * 2)
            s_parsed = _parse_chroma_results(s_results)
            chunks.extend(_rerank_chunks(query, s_parsed, top_k=per_scheme_k))
        # Sort combined results by distance
        chunks.sort(key=lambda c: c.distance)
        chunks = chunks[:n_results]
        primary_scheme_id = detected_schemes[0]

    else:
        # No specific scheme detected (operational guide or general mutual fund query):
        raw_results = query_corpus(query_text=query, scheme_id=None, n_results=max(n_results * 2, 10))
        parsed = _parse_chroma_results(raw_results)
        chunks = _rerank_chunks(query, parsed, top_k=n_results)
        # Infer primary scheme from top chunk if available
        primary_scheme_id = chunks[0].scheme_id if chunks and chunks[0].scheme_id != "operational-guide" else None

    return chunks, primary_scheme_id


def _parse_chroma_results(raw_results: Dict[str, Any]) -> List[RetrievedChunk]:
    """Helper to parse raw ChromaDB query response into typed RetrievedChunk objects."""
    chunks: List[RetrievedChunk] = []
    if not raw_results or not raw_results.get("ids") or not raw_results["ids"][0]:
        return chunks

    ids = raw_results["ids"][0]
    docs = raw_results["documents"][0]
    metas = raw_results["metadatas"][0]
    distances = raw_results["distances"][0] if "distances" in raw_results and raw_results["distances"] else [0.0] * len(ids)

    for chunk_id, text, meta, dist in zip(ids, docs, metas, distances):
        chunks.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                text=text,
                scheme_id=meta.get("scheme_id", ""),
                scheme_name=meta.get("scheme_name", ""),
                category=meta.get("category", ""),
                source_url=meta.get("source_url", ""),
                attribute_type=meta.get("attribute_type", ""),
                distance=float(dist),
            )
        )

    return chunks


def get_canonical_citation_for_scheme(scheme_id: Optional[str]) -> Tuple[str, str]:
    """
    Return the canonical citation name and URL for a scheme_id.
    Falls back to Groww Mutual Funds home if scheme_id is None or unknown.
    
    Args:
        scheme_id: Target scheme identifier.
        
    Returns:
        Tuple of (canonical_name, canonical_url).
    """
    if scheme_id and scheme_id in TARGET_SCHEMES:
        scheme = TARGET_SCHEMES[scheme_id]
        return scheme.scheme_name, scheme.source_url
    return "Groww Mutual Funds", "https://groww.in/mutual-funds"
