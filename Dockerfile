# DichTuDong - Real-time Meeting Translator
# Hỗ trợ 2 chế độ STT:
#   STT_ENGINE=mimo    → nhẹ, nhanh, cần internet + MIMO_API_KEY
#   STT_ENGINE=whisper → nặng (~1-2GB model), chạy hoàn toàn offline

FROM python:3.11-slim AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (phân tách để tận dụng Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Đảm bảo .env không bị copy vào image (dùng env_file trong compose)
RUN rm -f /app/.env

# Create data directories
RUN mkdir -p /app/data/logs /app/data/transcripts

# Expose port
EXPOSE 8765

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -sf http://localhost:8765/api/sessions || exit 1

# Start server
CMD ["python", "server.py"]
