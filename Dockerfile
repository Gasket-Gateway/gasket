# ── Build stage ────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Gasket Gateway" \
      org.opencontainers.image.description="Authenticated proxy and portal for OpenAI-compliant backends" \
      org.opencontainers.image.source="https://github.com/Gasket-Gateway/gasket"

# Copy installed packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app
COPY app/ ./app/

# Default config location — mount your own config.yaml here
COPY config.yaml /etc/gasket/config.yaml

EXPOSE 5000 9050

# Run with gunicorn on the main port; metrics server starts in-process
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--access-logfile", "-", \
     "app.main:app"]
