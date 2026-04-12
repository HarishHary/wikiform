FROM python:3.14-slim AS builder

WORKDIR /app

# Install system dependencies needed for pip builds (if any)
RUN apt-get update && \
    # apt-get install -y build-essential git --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a clean /install directory
COPY pyproject.toml poetry.lock* /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --without dev  --no-root --no-interaction --no-ansi

# === Final Stage ===
FROM python:3.14-slim

WORKDIR /app

# Optional: create non-root user for safety
RUN addgroup --system wikiform && adduser --system --ingroup wikiform wikiform

# Copy installed dependencies from builder
COPY --from=builder /usr/local /usr/local

# Copy code
COPY pyproject.toml ./
COPY README.md ./
COPY wikiform/ ./wikiform/

# Add a volume mount point
VOLUME ["/vault"]

# Install wikiform from source
RUN pip install --no-cache-dir --upgrade pip  && \
    pip install --no-cache-dir .

USER wikiform

ENTRYPOINT ["wikiform"]
CMD ["--help"]
