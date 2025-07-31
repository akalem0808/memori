# Build stage
FROM python:3.10-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.10-slim AS runtime

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
WORKDIR /app
COPY backend/ ./backend/

# Clean up cache and unnecessary files
RUN find /opt/venv -name "*.pyc" -delete && \
    find /opt/venv -name "__pycache__" -delete

# Expose both API and frontend ports
EXPOSE 8000 8080

# Run the API
CMD ["uvicorn", "backend.memory_api:app", "--host", "0.0.0.0", "--port", "8000"]
