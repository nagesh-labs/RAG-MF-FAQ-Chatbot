"""
FastAPI Application and Service Layer for Milestone RAG.
Exposes REST endpoints for chat interaction, thread management, scheme catalogs, and health checks.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import sys
from typing import List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings, TARGET_SCHEMES
from src.guardrails.pii_filter import sanitize_pii, is_otp_or_credential, get_otp_security_warning
from src.guardrails.intent_router import IntentType, classify_intent, generate_refusal_response
from src.ingestion.embedder import get_chroma_collection
from src.rag.retriever import retrieve_context, get_canonical_citation_for_scheme
from src.rag.generator import async_generate_answer
from src.session.thread_manager import thread_manager
from src.api.schemas import (
    ChatRequest,
    ChatResponse,
    ThreadCreateRequest,
    ThreadResponse,
    MessageResponse,
    SchemeInfo,
    HealthResponse,
)

logger = logging.getLogger("milestone_rag.api")
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle startup and shutdown handler."""
    logger.info("Initializing Milestone RAG API service...")
    await thread_manager.init_db()
    logger.info("Database initialized successfully.")
    yield
    logger.info("Shutting down Milestone RAG API service...")


app = FastAPI(
    title="Milestone RAG API",
    description=(
        "Compliant, Facts-Only Mutual Fund FAQ Assistant API for 5 HDFC Mutual Fund schemes. "
        "Strictly zero-hallucination, facts-only responses with Groq LPU synthesis, dual-layer guardrails, "
        "and persistent multi-thread conversational state."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration for UI and external client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------
# 1. Chat Interaction Endpoint
# ----------------------------------------------------------------------

@app.post("/api/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def process_chat_message(request: ChatRequest) -> ChatResponse:
    """
    Process an inbound user query through the full Milestone RAG pipeline:
    1. PII Sanitization (PAN, Aadhaar, Phone, Email, Folio, OTP)
    2. Antecedent pronoun resolution within thread context
    3. Intent classification & advisory refusal guardrail
    4. Metadata-filtered vector retrieval
    5. Groq LPU factual synthesis
    6. Post-generation compliance validation (<=3 sentences, 1 citation, footer)
    """
    raw_query = request.query.strip()
    if not raw_query:
        raise HTTPException(status_code=400, detail="Query text cannot be empty.")

    # Step 1: Ensure active conversation thread exists
    thread_id = request.thread_id
    if not thread_id:
        new_thread = await thread_manager.create_thread()
        thread_id = new_thread.thread_id
    else:
        existing = await thread_manager.get_thread(thread_id)
        if not existing:
            new_thread = await thread_manager.create_thread()
            thread_id = new_thread.thread_id

    # Step 2: PII Sanitization
    sanitized_query, pii_detected = sanitize_pii(raw_query)

    # Step 3: Handle sensitive credentials or OTP submission
    if is_otp_or_credential(raw_query):
        warning = get_otp_security_warning()
        # Save messages without recording sensitive token
        await thread_manager.add_message(
            thread_id=thread_id,
            role="user",
            content=sanitized_query,
            intent="SECURITY_ALERT",
        )
        await thread_manager.add_message(
            thread_id=thread_id,
            role="assistant",
            content=warning,
            intent="SECURITY_ALERT",
        )
        return ChatResponse(
            answer=warning,
            thread_id=thread_id,
            intent="SECURITY_ALERT",
            is_refusal=True,
            source_url=None,
            scheme_id=None,
            detected_pii=pii_detected,
        )

    # Step 4: Antecedent Pronoun Resolution (within isolated thread context)
    resolved_query, antecedent_scheme_id = await thread_manager.resolve_antecedent_context(
        query=sanitized_query,
        thread_id=thread_id,
    )

    # Step 5: Guardrail Intent Classification
    intent = classify_intent(resolved_query)

    # Step 6: Handle Non-Factual / Advisory Queries (Refusal Guardrail)
    if intent != IntentType.FACTUAL:
        refusal_answer = generate_refusal_response(intent=intent, query=resolved_query)

        await thread_manager.add_message(
            thread_id=thread_id,
            role="user",
            content=sanitized_query,
            intent=intent.value,
        )
        await thread_manager.add_message(
            thread_id=thread_id,
            role="assistant",
            content=refusal_answer,
            intent=intent.value,
        )

        return ChatResponse(
            answer=refusal_answer,
            thread_id=thread_id,
            intent=intent.value,
            is_refusal=True,
            source_url=None,
            scheme_id=None,
            detected_pii=pii_detected,
        )

    # Step 7: Factual Processing: Vector Retrieval
    chunks, primary_scheme_id = retrieve_context(resolved_query, n_results=5)
    target_scheme_id = primary_scheme_id or antecedent_scheme_id

    # Step 8: Groq LPU Synthesis with Compliance Validation
    answer = await async_generate_answer(
        query=resolved_query,
        retrieved_chunks=chunks,
        primary_scheme_id=target_scheme_id,
    )

    canonical_name, canonical_url = get_canonical_citation_for_scheme(target_scheme_id)

    # Step 9: Save user query and assistant response to thread history
    await thread_manager.add_message(
        thread_id=thread_id,
        role="user",
        content=sanitized_query,
        intent=IntentType.FACTUAL.value,
    )
    await thread_manager.add_message(
        thread_id=thread_id,
        role="assistant",
        content=answer,
        source_url=canonical_url,
        intent=IntentType.FACTUAL.value,
    )

    return ChatResponse(
        answer=answer,
        thread_id=thread_id,
        intent=IntentType.FACTUAL.value,
        is_refusal=False,
        source_url=canonical_url,
        scheme_id=target_scheme_id,
        detected_pii=pii_detected,
    )


# ----------------------------------------------------------------------
# 2. Thread Management Endpoints
# ----------------------------------------------------------------------

@app.get("/api/threads", response_model=List[ThreadResponse])
async def list_conversation_threads() -> List[ThreadResponse]:
    """List all active conversation threads sorted by most recent activity."""
    threads = await thread_manager.list_threads()
    return [
        ThreadResponse(
            thread_id=t.thread_id,
            title=t.title,
            created_at=t.created_at,
            updated_at=t.updated_at,
            message_count=t.message_count,
        )
        for t in threads
    ]


@app.post("/api/threads", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation_thread(request: Optional[ThreadCreateRequest] = None) -> ThreadResponse:
    """Create a new conversation thread."""
    title = request.title if request else None
    thread = await thread_manager.create_thread(title=title)
    return ThreadResponse(
        thread_id=thread.thread_id,
        title=thread.title,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        message_count=thread.message_count,
    )


@app.get("/api/threads/{thread_id}/history", response_model=List[MessageResponse])
async def get_thread_message_history(thread_id: str) -> List[MessageResponse]:
    """Retrieve full chronological message history for a specific thread."""
    thread = await thread_manager.get_thread(thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread '{thread_id}' not found.",
        )

    messages = await thread_manager.get_thread_history(thread_id)
    return [
        MessageResponse(
            message_id=m.message_id,
            thread_id=m.thread_id,
            role=m.role,
            content=m.content,
            source_url=m.source_url,
            intent=m.intent,
            created_at=m.created_at,
        )
        for m in messages
    ]


@app.delete("/api/threads/{thread_id}", status_code=status.HTTP_200_OK)
async def delete_conversation_thread(thread_id: str):
    """Delete a conversation thread and its associated message history."""
    deleted = await thread_manager.delete_thread(thread_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread '{thread_id}' not found.",
        )
    return {"deleted": True, "thread_id": thread_id}


# ----------------------------------------------------------------------
# 3. Schemes Catalog Endpoint
# ----------------------------------------------------------------------

@app.get("/api/schemes", response_model=List[SchemeInfo])
async def list_supported_schemes() -> List[SchemeInfo]:
    """Retrieve metadata and canonical URLs for all 5 indexed HDFC Mutual Fund schemes."""
    return [
        SchemeInfo(
            scheme_id=s.scheme_id,
            scheme_name=s.scheme_name,
            category=s.category,
            source_url=s.source_url,
            aliases=s.aliases,
        )
        for s in TARGET_SCHEMES.values()
    ]


# ----------------------------------------------------------------------
# 4. System Health Check Endpoint
# ----------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
async def check_health() -> HealthResponse:
    """System health check and diagnostic status."""
    try:
        collection = get_chroma_collection()
        chunk_count = collection.count()
    except Exception as exc:
        chunk_count = 0
        logger.error(f"Error accessing ChromaDB: {exc}")

    return HealthResponse(
        status="ok",
        database="connected",
        vector_store_collection=settings.chroma_collection_name,
        vector_store_chunks=chunk_count,
        supported_schemes_count=len(TARGET_SCHEMES),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ----------------------------------------------------------------------
# 5. Global Exception Handler
# ----------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    """Catch-all unhandled exception handler returning structured JSON."""
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred while processing the request."},
    )
