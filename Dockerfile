# Grapoll Backend Dockerfile
# Deployed on Fly.io (Tokyo nrt)

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser \
    && mkdir -p /app/sessions /app/logs /home/appuser/.cache \
    && chown -R appuser:appuser /app /home/appuser

USER appuser

# Expose port (Fly.io sets $PORT via fly.toml env)
EXPOSE 8000

# Run the application — use shell form to expand $PORT
CMD uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
