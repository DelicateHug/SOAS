# Local embedding service — sentence-transformers running entirely on-prem.
# No outbound network calls at runtime; the model is baked into the image.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models \
    TRANSFORMERS_OFFLINE=0

WORKDIR /app

# System deps for tokenizer wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY embeddings/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Pre-download the model so the container starts cold-warm. The default model is
# all-MiniLM-L6-v2: 384 dims, ~22MB, fast on CPU. Override via SENTENCE_MODEL build arg.
ARG SENTENCE_MODEL=sentence-transformers/all-MiniLM-L6-v2
ENV SENTENCE_MODEL=${SENTENCE_MODEL}
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${SENTENCE_MODEL}', cache_folder='/models')"

# Once the model is cached, never reach out to HF Hub at runtime.
ENV TRANSFORMERS_OFFLINE=1 \
    HF_HUB_OFFLINE=1

COPY embeddings/server.py /app/server.py

EXPOSE 8200

# Single uvicorn worker — sentence-transformers loads ~80MB into RAM and isn't worth
# multiplying. Concurrency comes from FastAPI's async handling and short request times.
# mTLS: serve TLS and require a client cert signed by the SOAS internal CA.
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port 8200 --workers 1 \
  --ssl-keyfile=/run/mtls/embeddings/server.key \
  --ssl-certfile=/run/mtls/embeddings/server.crt \
  --ssl-ca-certs=/run/mtls/ca/ca.crt \
  --ssl-cert-reqs=2"]
