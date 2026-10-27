# ==============================================================================
# Dockerfile: Milestone RAG HDFC Mutual Fund Assistant (Production for Railway)
# ==============================================================================
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable immediate stdout flushing
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8501 \
    API_PORT=8000 \
    API_HOST=0.0.0.0 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install minimal OS dependencies for sentence-transformers, SQLite, and health probes
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Pre-install lightweight CPU-only PyTorch to minimize image size (~250MB vs ~3GB CUDA)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install application dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download SentenceTransformer model weights at BUILD time so runtime has 0 network latency
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application source code, configs, and verified factsheet data
COPY src/ ./src/
COPY frontend/ ./frontend/
COPY data/processed/ ./data/processed/
COPY data/raw/ ./data/raw/
COPY .streamlit/ ./.streamlit/
COPY scripts/ ./scripts/
COPY start.sh .

# Pre-build ChromaDB vector index at BUILD time (instant boot on Railway)
RUN python -m src.ingestion.embedder

# Ensure start script has executable permissions and unix line endings
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

# Create runtime directories for persistent sqlite and vector store
RUN mkdir -p data/vector_store data/eval

# Expose ports (Railway maps public traffic to $PORT)
EXPOSE 8501 8000

# Execute entrypoint startup script
CMD ["./start.sh"]
