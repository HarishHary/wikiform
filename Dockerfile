FROM python:3.14-slim AS builder

WORKDIR /app

RUN apt-get update && \
    apt-get install -y build-essential libsqlite3-dev default-jre-headless --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock /app/
RUN uv export --frozen --no-dev --no-emit-project --no-hashes -o /tmp/requirements.txt && \
    uv pip install --system --no-cache -r /tmp/requirements.txt

# Pre-download embedding model into a fixed cache location
ENV HF_HOME=/hf-cache
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-en-v1.5')"


# === Final Stage ===
FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y libsqlite3-dev default-jre-headless --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN addgroup --system wikiform && adduser --system --ingroup wikiform wikiform

# Copy installed Python packages (and uv) from builder
COPY --from=builder /usr/local /usr/local

# Put `uv tool install` executables on PATH (used by `make install` in the dev container)
ENV UV_TOOL_BIN_DIR=/usr/local/bin

# Copy pre-downloaded HuggingFace model cache
COPY --from=builder /hf-cache /hf-cache

# Copy source
COPY pyproject.toml ./
COPY README.md ./
COPY wikiform/ ./wikiform/

VOLUME ["/vault"]

RUN pip install --no-cache-dir . && \
    chown -R wikiform:wikiform /hf-cache

USER wikiform

ENV HF_HOME=/hf-cache

ENTRYPOINT ["wikiform"]
CMD ["--help"]
