FROM python:3.11-slim

WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project manifests
COPY pyproject.toml uv.lock ./

# Install dependencies using uv frozen sync
RUN uv sync --frozen --no-dev

# Copy source tree and services
COPY src/ ./src/
COPY services/ ./services/
COPY config/ ./config/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:/app"
ENV DRIFTSENSE_DATA_DIR="/app/data/uploads"

EXPOSE 8000

CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
