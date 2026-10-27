"""
LLM Synthesis Engine for Milestone RAG.
Interfaces with Groq LPUs (llama-3.3-70b-versatile / llama-3.1-8b-instant) to generate
grounded, facts-only mutual fund responses with deterministic extractive fallback.
"""

from datetime import date
import logging
import os
import re
from typing import List, Optional, Tuple

from groq import Groq, AsyncGroq
from src.config import settings, TARGET_SCHEMES
from src.rag.retriever import RetrievedChunk, get_canonical_citation_for_scheme
from src.rag.validator import format_and_validate_response

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a facts-only mutual fund assistant with Groww as reference product context for 5 HDFC Mutual Fund schemes.
Answer the user's question accurately and objectively using ONLY the facts present in the Context below.

NON-NEGOTIABLE COMPLIANCE RULES:
1. Facts Only: Never give investment advice, buy/sell recommendations, or personal opinions.
2. Groundedness: If the requested information is not in the Context, explicitly state: "Information for this query is not available in the verified Groww sources."
3. Length: Your narrative answer must be at most 3 sentences.
4. Source Link: Include exactly one citation link to the official scheme page in the format: Source: [Scheme Name](URL)"""


def build_context_block(chunks: List[RetrievedChunk]) -> str:
    """Format retrieved semantic chunks into an annotated context block."""
    if not chunks:
        return "No relevant context found in verified corpus."

    formatted_parts: List[str] = []
    for idx, c in enumerate(chunks, 1):
        formatted_parts.append(
            f"[Chunk {idx}] Scheme: {c.scheme_name} | Category: {c.category}\n"
            f"Content: {c.text}\n"
            f"Source URL: {c.source_url}"
        )
    return "\n\n".join(formatted_parts)


def _extractive_fallback_synthesizer(
    query: str,
    chunks: List[RetrievedChunk],
    canonical_name: str,
    canonical_url: str,
) -> str:
    """
    Deterministic extractive fallback when Groq API key is not configured or in offline mode.
    Ranks sentences across the retrieved chunks by query relevance and selects at most 3.
    """
    if not chunks:
        return (
            "Information for this query is not available in the verified Groww sources."
        )

    stopwords = {"what", "is", "the", "for", "of", "and", "in", "to", "who", "does", "have", "a", "an", "on", "from", "with", "this", "that", "how", "can", "do", "i", "where", "are"}
    scheme_words = {"hdfc", "mid", "cap", "opportunities", "small", "top", "100", "large", "silver", "etf", "fof", "multi", "direct", "growth", "fund", "scheme", "mutual"}
    
    query_words = set(re.findall(r"\w+", query.lower())) - stopwords
    attribute_words = query_words - scheme_words

    scored_sentences = []
    seen = set()

    for c in chunks:
        # Split chunk into sentences
        chunk_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", c.text) if s.strip()]
        for s in chunk_sentences:
            s_clean = s.strip()
            if s_clean and s_clean not in seen:
                seen.add(s_clean)
                s_words = set(re.findall(r"\w+", s_clean.lower())) - stopwords
                
                # Base overlap with query words
                overlap = len(s_words & query_words)
                
                # Attribute word bonus: heavily reward sentences matching specific attribute intent
                attr_bonus = 0
                for a in attribute_words:
                    prefix = a[:4] if len(a) >= 4 else a
                    if any(w.startswith(prefix) for w in s_words):
                        attr_bonus += 15

                total_score = overlap + attr_bonus
                scored_sentences.append((total_score, s_clean))

    # Prioritize sentences with higher query overlap
    scored_sentences.sort(key=lambda x: x[0], reverse=True)

    # Take top sentences that have match, or fallback to first sentences
    positive_matches = [s for score, s in scored_sentences if score > 0]
    if positive_matches:
        selected = positive_matches[:3]
    else:
        selected = [s for _, s in scored_sentences[:3]]

    body = " ".join(selected)
    return body


def generate_answer(
    query: str,
    retrieved_chunks: List[RetrievedChunk],
    primary_scheme_id: Optional[str] = None,
    client: Optional[Groq] = None,
) -> str:
    """
    Generate a grounded, facts-only answer to user query using Groq LLM
    with automated post-generation compliance validation.
    
    Args:
        query: User question.
        retrieved_chunks: Chunks retrieved by Hybrid Scheme Retriever.
        primary_scheme_id: Canonical scheme_id if resolved.
        client: Optional pre-configured Groq client (for dependency injection/testing).
        
    Returns:
        Validated, strictly compliant response string.
    """
    canonical_name, canonical_url = get_canonical_citation_for_scheme(primary_scheme_id)

    # If no chunks were retrieved at all
    if not retrieved_chunks:
        raw_answer = "Information for this query is not available in the verified Groww sources."
        return format_and_validate_response(
            raw_response=raw_answer,
            canonical_url=canonical_url,
            canonical_name=canonical_name,
        )

    # Check for Groq API key
    api_key = settings.groq_api_key or os.getenv("GROQ_API_KEY", "")

    if not api_key and client is None:
        logger.info("GROQ_API_KEY not configured. Running deterministic extractive synthesizer.")
        raw_answer = _extractive_fallback_synthesizer(
            query=query,
            chunks=retrieved_chunks,
            canonical_name=canonical_name,
            canonical_url=canonical_url,
        )
    else:
        try:
            groq_client = client or Groq(api_key=api_key)
            context_block = build_context_block(retrieved_chunks)

            user_prompt = f"Context:\n{context_block}\n\nQuestion: {query}"

            completion = groq_client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=settings.groq_temperature,
                max_tokens=settings.groq_max_tokens,
            )
            raw_answer = completion.choices[0].message.content or ""

        except Exception as exc:
            logger.warning(f"Groq generation failed ({exc}). Falling back to extractive synthesizer.")
            raw_answer = _extractive_fallback_synthesizer(
                query=query,
                chunks=retrieved_chunks,
                canonical_name=canonical_name,
                canonical_url=canonical_url,
            )

    # Post-generation compliance validation (sentence count, citation, footer)
    validated_response = format_and_validate_response(
        raw_response=raw_answer,
        canonical_url=canonical_url,
        canonical_name=canonical_name,
    )

    return validated_response


async def async_generate_answer(
    query: str,
    retrieved_chunks: List[RetrievedChunk],
    primary_scheme_id: Optional[str] = None,
    client: Optional[AsyncGroq] = None,
) -> str:
    """
    Asynchronous version of answer generation utilizing AsyncGroq.
    
    Args:
        query: User question.
        retrieved_chunks: Chunks retrieved by Hybrid Scheme Retriever.
        primary_scheme_id: Canonical scheme_id if resolved.
        client: Optional pre-configured AsyncGroq client.
        
    Returns:
        Validated, strictly compliant response string.
    """
    canonical_name, canonical_url = get_canonical_citation_for_scheme(primary_scheme_id)

    if not retrieved_chunks:
        raw_answer = "Information for this query is not available in the verified Groww sources."
        return format_and_validate_response(
            raw_response=raw_answer,
            canonical_url=canonical_url,
            canonical_name=canonical_name,
        )

    api_key = settings.groq_api_key or os.getenv("GROQ_API_KEY", "")

    if not api_key and client is None:
        raw_answer = _extractive_fallback_synthesizer(
            query=query,
            chunks=retrieved_chunks,
            canonical_name=canonical_name,
            canonical_url=canonical_url,
        )
    else:
        try:
            groq_client = client or AsyncGroq(api_key=api_key)
            context_block = build_context_block(retrieved_chunks)
            user_prompt = f"Context:\n{context_block}\n\nQuestion: {query}"

            completion = await groq_client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=settings.groq_temperature,
                max_tokens=settings.groq_max_tokens,
            )
            raw_answer = completion.choices[0].message.content or ""

        except Exception as exc:
            logger.warning(f"Async Groq generation failed ({exc}). Falling back to extractive synthesizer.")
            raw_answer = _extractive_fallback_synthesizer(
                query=query,
                chunks=retrieved_chunks,
                canonical_name=canonical_name,
                canonical_url=canonical_url,
            )

    return format_and_validate_response(
        raw_response=raw_answer,
        canonical_url=canonical_url,
        canonical_name=canonical_name,
    )
