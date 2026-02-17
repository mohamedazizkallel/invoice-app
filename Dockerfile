# ==============================================
# STAGE 1: Builder
# ==============================================
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project
COPY invoice/ ./invoice/
WORKDIR /app/invoice

# Build-time static collection (uses SQLite since DEBUG not set = defaults True)
RUN SECRET_KEY=build-placeholder \
    DEBUG=False \
    ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput


# ==============================================
# STAGE 2: Runtime
# ==============================================
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/invoice

# Install runtime dependency only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy venv + app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/invoice /app/invoice

ENV PATH="/opt/venv/bin:$PATH"

# Copy entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Safer healthcheck (no python dependency)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:8000 || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
