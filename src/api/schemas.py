"""
Pydantic Data Contracts and Schemas for Milestone RAG API.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Inbound chat query payload."""
    query: str = Field(..., min_length=1, description="User query or question text")
    thread_id: Optional[str] = Field(None, description="Optional thread UUID; auto-created if omitted")


class ChatResponse(BaseModel):
    """Outbound chat response payload."""
    answer: str = Field(..., description="Compliant facts-only answer or deterministic refusal message")
    thread_id: str = Field(..., description="Active conversation thread ID")
    intent: str = Field(..., description="Intent classification (e.g. FACTUAL, ADVISORY, etc.)")
    is_refusal: bool = Field(..., description="True if query was intercepted by guardrails")
    source_url: Optional[str] = Field(None, description="Official canonical reference link")
    scheme_id: Optional[str] = Field(None, description="Resolved target scheme ID if applicable")
    detected_pii: List[str] = Field(default_factory=list, description="Any detected and redacted PII types")


class ThreadCreateRequest(BaseModel):
    """Payload to spawn a new conversation thread."""
    title: Optional[str] = Field(None, description="Optional title for the new thread")


class ThreadResponse(BaseModel):
    """Summary of a conversation thread."""
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class MessageResponse(BaseModel):
    """Individual conversation message representation."""
    message_id: str
    thread_id: str
    role: str
    content: str
    source_url: Optional[str] = None
    intent: Optional[str] = None
    created_at: str


class SchemeInfo(BaseModel):
    """Metadata for an indexed HDFC Mutual Fund scheme."""
    scheme_id: str
    scheme_name: str
    category: str
    source_url: str
    aliases: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """System health check and diagnostic status."""
    status: str
    database: str
    vector_store_collection: str
    vector_store_chunks: int
    supported_schemes_count: int
    timestamp: str
