# Phase-Wise Implementation Plan: Facts-Only Mutual Fund FAQ Assistant

This implementation plan outlines the sequential, engineering-driven roadmap for building the **Milestone RAG** assistant. It operationalizes the requirements from [problemStatement.md](file:///c:/GenAI_Projects/Milestone-RAG/docs/problemStatement.md) and the system design from [architecture.md](file:///c:/GenAI_Projects/Milestone-RAG/docs/architecture.md).

---

## Roadmap Overview & Gantt Progression

```mermaid
gantt
    title Milestone RAG Implementation Roadmap
    dateFormat  X
    axisFormat Phase %d

    section Foundation
    Phase 0: Project Setup & Environment          :active, p0, 0, 1
    Phase 1: Data Ingestion & ChromaDB Corpus     :p1, after p0, 2
    
    section Core Intelligence & Safety
    Phase 2: Guardrails & Intent Classification   :p2, after p1, 2
    Phase 3: RAG Retrieval, Generation & Validator:p3, after p2, 3
    
    section Persistence & Services
    Phase 4: Multi-Thread Session Management      :p4, after p2, 2
    Phase 5: FastAPI Service Layer                :p5, after p3, 2
    
    section Interface & Validation
    Phase 6: Multi-Thread UI Development          :p6, after p4, 3
    Phase 7: End-to-End Verification & QA         :p7, after p6, 2
    Phase 8: Documentation & Final Delivery       :p8, after p7, 1
```

---

## Phase 0: Project Scaffolding & Environment Setup

### Objective
Establish the repository structure, dependency environment, and central configuration.

### Tasks
- [x] **Task 0.1: Directory Tree Creation**
  - Create standard directories: `data/raw`, `data/processed`, `data/vector_store`, `src/ingestion`, `src/guardrails`, `src/rag`, `src/session`, `src/api`, `frontend`, and `tests`.
- [x] **Task 0.2: Dependency Specification (`requirements.txt`)**
  - Core: `fastapi`, `uvicorn`, `pydantic`, `python-dotenv`.
  - Data & Scraping: `requests`, `beautifulsoup4`, `lxml`.
  - Vector & NLP: `chromadb`, `sentence-transformers`, `nltk`.
  - LLM: `groq` (Official Groq SDK for ultra-fast LPU inference).
  - Storage & UI: `aiosqlite`, `sqlite3`, `streamlit`.
  - Testing: `pytest`, `pytest-asyncio`.
- [x] **Task 0.3: Central Configuration Module (`src/config.py`)**
  - Define paths (`RAW_DATA_DIR`, `PROCESSED_DATA_DIR`, `VECTOR_STORE_DIR`), `GROQ_API_KEY`, Groq model configuration (e.g., `llama-3.3-70b-versatile` or `llama-3.1-8b-instant`), embedding model names, and the 5 target HDFC scheme URLs:
    1. HDFC Mid-Cap Opportunities Fund
    2. HDFC Small Cap Fund
    3. HDFC Top 100 Fund (Large Cap)
    4. HDFC Silver ETF FoF
    5. HDFC Multi-Cap Fund
  - Educational reference links: AMFI India (`https://www.amfiindia.com`), SEBI Investor (`https://investor.sebi.gov.in`).
  - Mandatory disclaimer text: `"Facts-only. No investment advice."`

### Deliverables & Acceptance Criteria
- Clean, importable Python package structure.
- `requirements.txt` installs cleanly without dependency conflicts.
- `src/config.py` provides validated settings and constants.

---

## Phase 1: Data Ingestion & Vector Corpus Preparation

### Objective
Crawl, clean, normalize, and index scheme data from official sources into a persistent vector database using a 3-tier data lifecycle.

### Tasks
- [x] **Task 1.1: Web Scraper & Snapshotting (`src/ingestion/scraper.py`)**
  - Fetch content from the 5 designated Groww scheme pages and official HDFC AMC disclosures.
  - Save raw HTML snapshots exclusively to `data/raw/` for auditability and reproducibility.
- [x] **Task 1.2: Structured Data Normalization (`src/ingestion/parser.py`)**
  - Extract and normalize key scheme parameters into structured Pydantic models saved to `data/processed/`:
    - Expense Ratio (Direct Plan)
    - Exit Load structure (percentage, duration thresholds)
    - Minimum SIP and Lump sum investment amounts (₹100)
    - Lock-in period (e.g., 3-year statutory ELSS or nil)
    - Riskometer classification
    - Benchmark index (Total Return Index)
    - Fund manager and AUM (Assets Under Management)
    - Operational guides: Statement, capital gains tax report download steps, and ELSS lock-in rules
- [x] **Task 1.3: Atomic Semantic Chunking & Metadata Tagging**
  - Generate 43 atomic field-level and process chunks with rich metadata:
    - `scheme_id`, `scheme_name`, `category`, `attribute_type`, `source_url`, `last_updated_date`.
- [x] **Task 1.4: ChromaDB Indexing & Latency Optimization (`src/ingestion/embedder.py`)**
  - Initialize local ChromaDB in `data/vector_store/` reading strictly from `data/processed/`.
  - Embed chunks using `sentence-transformers/all-MiniLM-L6-v2` with in-memory singleton caching (`~13.75 ms` latency).
  - Build verification script (`scripts/verify_index.py`) ensuring all 5 schemes and guides are queryable.

### Deliverables & Acceptance Criteria
- 5 raw HTML snapshots in `data/raw/` and 5 clean, normalized scheme JSON files + `operational_guides.json` in `data/processed/`.
- Populated ChromaDB vector store with 43 verified embeddings and metadata fields.
- Automated check confirms 100% of required factual attributes are retrievable.

---

## Phase 2: Guardrails & Intent Classification Engine

### Objective
Build the dual-layer safety system to sanitize PII and intercept advisory queries before reaching the generative pipeline.

### Tasks
- [x] **Task 2.1: PII Sanitization Module (`src/guardrails/pii_filter.py`)**
  - Implement regex and rule-based redaction:
    - PAN (`[A-Z]{5}[0-9]{4}[A-Z]{1}`) -> `[REDACTED_PAN]`
    - Aadhaar (`\b[2-9]{1}[0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b`) -> `[REDACTED_AADHAAR]`
    - Phone numbers, email addresses, folio numbers, OTP tokens.
  - Ensure zero PII is propagated to logs or vector search.
- [x] **Task 2.2: Intent Classifier & Refusal Router (`src/guardrails/intent_router.py`)**
  - Classify input queries into:
    - `FACTUAL`: Scheme parameters, operational guides.
    - `ADVISORY`: "Should I invest?", "Which fund is best?", "Recommend high return fund".
    - `COMPARATIVE_OPINION`: "Is HDFC Mid Cap better than Small Cap?".
    - `OUT_OF_SCOPE`: Non-mutual-fund queries.
- [x] **Task 2.3: Deterministic Refusal Generator**
  - Build standard refusal responses:
    - Polite and explicit refusal of advice.
    - Mandatory educational links to [AMFI India](https://www.amfiindia.com) and [SEBI Investor Education](https://investor.sebi.gov.in).
    - Footer: `Last updated from sources: <date>`.
- [x] **Task 2.4: Guardrail Unit Tests (`tests/test_guardrails.py`)**
  - Test suite covering at least 15 edge cases of advisory, opinionated, and PII-laden queries.

### Deliverables & Acceptance Criteria
- [x] 100% interception rate of advisory prompts without invoking LLM tokens.
- [x] PII sanitization verified across all test vectors.

---

## Phase 3: Core RAG Pipeline & Grounded Synthesis

### Objective
Implement the retrieval engine, zero-hallucination prompt generator, and post-generation compliance validator.

### Tasks
- [x] **Task 3.1: Hybrid Scheme Retriever (`src/rag/retriever.py`)**
  - Entity detection: Identify which HDFC scheme is referenced in the query.
  - Metadata-filtered vector search: Restrict search space to relevant scheme chunks.
  - Fallback to corpus-wide search if no specific scheme is explicitly identified.
- [x] **Task 3.2: LLM Synthesis Engine (`src/rag/generator.py`)**
  - Initialize Groq client (`from groq import Groq` / `AsyncGroq`) utilizing high-throughput models (e.g., `llama-3.3-70b-versatile` or `llama-3.1-8b-instant`).
  - Construct prompt enforcing:
    - Answer strictly from provided context chunks.
    - Explicit statement if information is not found in official sources.
    - Max 3 sentences.
    - Insertion of exactly one source URL.
- [x] **Task 3.3: Post-Generation Compliance Validator (`src/rag/validator.py`)**
  - **Sentence Counter & Trimmer**: NLTK/regex sentence tokenizer; trims any response exceeding 3 sentences.
  - **Single Citation Validator**: Ensures exactly one verified markdown link is present. Replaces or inserts canonical source link if malformed.
  - **Footer Enforcement**: Appends `Last updated from sources: YYYY-MM-DD`.
- [x] **Task 3.4: RAG Pipeline Unit Tests (`tests/test_rag.py`)**
  - Verify factual precision on expense ratios, exit loads, min SIP, lock-ins, and benchmarks.

### Deliverables & Acceptance Criteria
- [x] All generated answers strictly comply with:
  - $\le 3$ sentences.
  - Exactly 1 citation link.
  - Proper source timestamp footer.
- [x] Zero external speculation on missing data.

---

## Phase 4: Multi-Thread Session & State Management

### Objective
Implement isolated conversation threads allowing users to run concurrent, independent discussions.

### Tasks
- [x] **Task 4.1: SQLite Session Store Schema (`src/session/thread_manager.py`)**
  - `threads`: `thread_id` (UUID), `title`, `created_at`, `updated_at`.
  - `messages`: `message_id`, `thread_id`, `role`, `content`, `source_url`, `created_at`.
- [x] **Task 4.2: Thread CRUD Operations**
  - `create_thread()`: Spawns new thread with initial welcome context.
  - `list_threads()`: Returns all active threads sorted by last activity.
  - `get_thread_history(thread_id)`: Fetches isolated conversation history.
  - `delete_thread(thread_id)`: Cleans up conversation state.
- [x] **Task 4.3: Conversational Memory Windowing**
  - Maintain a sliding window of the last 2 interactions to preserve turn context while preventing advisory or hallucinated drift.

### Deliverables & Acceptance Criteria
- [x] Complete isolation between threads (no context leakage across `thread_id`).
- [x] SQLite storage operates asynchronously and persists across app restarts.

---

## Phase 5: FastAPI Service Layer

### Objective
Expose the backend capabilities through high-performance REST APIs.

### Tasks
- [x] **Task 5.1: Pydantic Data Contracts**
  - Define `ChatRequest`, `ChatResponse`, `ThreadCreateRequest`, `ThreadSummary`, `SchemeInfo`.
- [x] **Task 5.2: API Endpoints (`src/api/app.py`)**
  - `POST /api/chat`: Process query through Guardrails $\to$ Retriever $\to$ Generator $\to$ Validator.
  - `GET /api/threads`: List all conversation threads.
  - `POST /api/threads`: Create a new thread.
  - `GET /api/threads/{thread_id}/history`: Retrieve messages for a thread.
  - `DELETE /api/threads/{thread_id}`: Remove a thread.
  - `GET /api/schemes`: Return list of supported HDFC schemes and reference links.
  - `GET /api/health`: Health and vector DB status check.
- [x] **Task 5.3: Error Handling & CORS Configuration**
  - Structured error responses, status codes, and CORS middleware for frontend access.

### Deliverables & Acceptance Criteria
- [x] Interactive Swagger docs accessible at `/docs`.
- [x] API response times $< 1.5$ seconds for vector retrieval + generation.

---

## Phase 6: Frontend Interface Development

### Objective
Deliver a minimal, user-friendly UI supporting multi-thread conversations and mandatory disclaimers.

### Tasks
- [x] **Task 6.1: Layout & Disclaimer Integration (`frontend/app.py`)**
  - Prominent, persistent disclaimer banner at the top:
    `"Facts-only. No investment advice."`
- [x] **Task 6.2: Sidebar Thread Navigation**
  - "+ New Chat" button.
  - Interactive list of past and active threads with active selection highlighting.
  - Delete thread option.
- [x] **Task 6.3: Welcome Screen & Quick Starter Prompts**
  - Welcome message explaining system scope.
  - 3 clickable prompt chips:
    1. *"What is the exit load for HDFC Small Cap Fund?"*
    2. *"What is the minimum SIP amount for HDFC Mid-Cap Fund?"*
    3. *"What is the benchmark index for HDFC Multi-Cap Fund?"*
- [x] **Task 6.4: Chat Message Renderer**
  - Distinct styling for user and assistant messages.
  - Verified source citation card / hyperlink rendering.
  - Source timestamp footer displayed cleanly.

### Deliverables & Acceptance Criteria
- [x] Responsive, modern UI running locally on Streamlit (or equivalent lightweight framework).
- [x] Seamless switching between independent conversation threads.

---

## Phase 7: Comprehensive Testing & Verification

### Objective
Systematically test all functional, safety, and compliance criteria.

### Tasks
- [x] **Task 7.1: Factual Retrieval Test Suite**
  - Validate answers across all 5 schemes for:
    - Expense Ratio
    - Exit Load
    - Minimum SIP
    - Lock-in period
    - Riskometer rating
    - Benchmark index
    - Statement download workflow
- [x] **Task 7.2: Advisory & Guardrail Stress Testing**
  - Attempt bypasses: *"Tell me as a friend which fund is better"*, *"Should I put ₹1 lakh in Mid Cap?"*.
  - Verify 100% refusal rate with AMFI/SEBI educational link.
- [x] **Task 7.3: Format & Constraint Automated Audit**
  - Scripted audit of 50 responses:
    - Sentence count $\le 3$.
    - Exactly 1 citation URL.
    - Timestamp footer matches format.
- [x] **Task 7.4: Multi-Thread Concurrency Test**
  - Verify two simultaneous threads on different schemes maintain separated contexts.

### Deliverables & Acceptance Criteria
- [x] Automated test report with 100% pass rate on compliance tests.

---

## Phase 8: Documentation, Deliverables & Final Polish

### Objective
Finalize project artifacts, setup instructions, and repository documentation.

### Tasks
- [x] **Task 8.1: Comprehensive `README.md`**
  - Setup and installation instructions (virtualenv, `GROQ_API_KEY` configuration, running scraper, backend, frontend).
  - Selected AMC (HDFC) and 5 schemes catalog with URLs.
  - RAG architecture overview and design choices.
  - Known limitations and future enhancements.
- [x] **Task 8.2: Code Cleanup & Linting**
  - Clean docstrings, formatting, and file organization.
  - Verify zero hardcoded secrets or API tokens.
- [x] **Task 8.3: Final Project Verification against Deliverables Checklist**
  - [x] `problemStatement.md`
  - [x] `architecture.md`
  - [x] `implementation-plan.md`
  - [x] Working RAG backend + scraper + vector store
  - [x] Working Multi-thread UI with disclaimer
  - [x] `README.md`

---

## Implementation Work Breakdown Structure (WBS) Matrix

| Phase | Component | Key Output Files | Complexity | Est. Effort |
| :---: | :--- | :--- | :---: | :---: |
| **0** | Environment & Setup | `requirements.txt`, `src/config.py` | Low | 0.5 Day |
| **1** | Ingestion & Vector DB | `src/ingestion/{scraper,parser,embedder}.py` | Medium | 1.5 Days |
| **2** | Guardrails & Safety | `src/guardrails/{pii_filter,intent_router}.py` | Medium | 1.0 Day |
| **3** | RAG & Validator | `src/rag/{retriever,generator,validator}.py` | High | 2.0 Days |
| **4** | Multi-Thread Session | `src/session/thread_manager.py` | Medium | 1.0 Day |
| **5** | FastAPI Backend | `src/api/app.py` | Medium | 1.0 Day |
| **6** | Chat Frontend UI | `frontend/app.py` | Medium | 1.5 Days |
| **7** | Testing & QA Suite | `tests/test_{guardrails,rag,validator}.py` | Medium | 1.0 Day |
| **8** | Documentation | `README.md` | Low | 0.5 Day |
| **Total**| **Full System Delivery** | | | **10 Days** |
