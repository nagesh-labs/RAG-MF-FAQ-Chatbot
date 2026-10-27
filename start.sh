#!/usr/bin/env bash
set -e

echo "=========================================================="
echo " Starting Milestone RAG Service on Railway"
echo " Time: $(date -u)"
echo " Environment: PORT=${PORT:-8501}, API_PORT=${API_PORT:-8000}"
echo "=========================================================="

# 1. Verify or automatically build the ChromaDB Vector Index
if [ ! -f "data/vector_store/chroma.sqlite3" ]; then
    echo "[1/4] Vector store not found. Indexing 5 HDFC schemes from data/processed/..."
    python -m src.ingestion.embedder
    echo "[1/4] Vector store indexing completed successfully."
else
    echo "[1/4] Vector store found at data/vector_store/chroma.sqlite3. Ready."
fi

# 2. Launch FastAPI Microservice in Background
echo "[2/4] Starting FastAPI backend on 127.0.0.1:${API_PORT:-8000}..."
python -m uvicorn src.api.app:app --host 127.0.0.1 --port ${API_PORT:-8000} &
BACKEND_PID=$!

# 3. Wait for FastAPI to become healthy
echo "[3/4] Waiting for backend API healthcheck probe..."
for i in {1..30}; do
    if curl -s "http://127.0.0.1:${API_PORT:-8000}/api/health" | grep -q "HEALTHY"; then
        echo "[3/4] Backend API is ONLINE and HEALTHY."
        break
    fi
    echo "  Waiting for API server... (${i}/30)"
    sleep 1
done

# Trap SIGTERM and SIGINT to gracefully terminate both background and foreground processes
trap "echo 'Stopping services...'; kill -TERM $BACKEND_PID 2>/dev/null; exit 0" SIGTERM SIGINT

# 4. Launch Streamlit Frontend in Foreground (Binding to Railway's $PORT)
TARGET_PORT=${PORT:-8501}
echo "[4/4] Starting Streamlit UI on 0.0.0.0:${TARGET_PORT}..."
streamlit run frontend/app.py \
    --server.port ${TARGET_PORT} \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --browser.gatherUsageStats false
