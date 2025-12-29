# Oil Record Book Tool - Production Dockerfile
# Multi-stage build for minimal image size

# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# Stage 2: Production image
FROM python:3.11-slim as production

# Labels
LABEL maintainer="DP" \
      version="1.0" \
      description="Oil Record Book Tool - Maritime fuel and compliance tracking"

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup templates/ ./templates/
COPY --chown=appuser:appgroup static/ ./static/
COPY --chown=appuser:appgroup migrations/ ./migrations/
COPY --chown=appuser:appgroup data/sounding_tables.json ./data/
COPY --chown=appuser:appgroup gunicorn.conf.py .
COPY --chown=appuser:appgroup scripts/healthcheck.py ./scripts/

# Create data directory for SQLite database
RUN mkdir -p /app/data && chown -R appuser:appgroup /app/data

# Environment variables
ENV FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python scripts/healthcheck.py || exit 1

# Run with gunicorn
CMD ["gunicorn", "--config", "gunicorn.conf.py", "src.app:create_app()"]
