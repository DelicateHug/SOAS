FROM python:3.12-slim

WORKDIR /app

# Install git (needed for git sync feature) and Node.js (needed to install the
# `claude` CLI used by the AI subprocess shell-out).
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates curl gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && apt-get install -y --no-install-recommends nodejs && \
    npm install -g @anthropic-ai/claude-code && \
    apt-get purge -y curl gnupg && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /root/.npm

# Install shared package
COPY shared/ /tmp/shared/
RUN pip install --no-cache-dir /tmp/shared/ && rm -rf /tmp/shared/

# Install VisualPython2 headless modules (node catalog, compiler, schema)
COPY VisualPython2/src/visualpython2/ /opt/vp2/visualpython2/
ENV PYTHONPATH="/opt/vp2:${PYTHONPATH}"

# Copy backend source + config first (setuptools needs src/ to resolve packages)
COPY backend/pyproject.toml ./
COPY backend/src/ ./src/
COPY backend/alembic.ini ./
COPY backend/alembic/ ./alembic/

# Install backend package + dependencies
RUN pip install --no-cache-dir .

ENV PYTHONPATH="/app/src:/opt/vp2"
EXPOSE 8000

# Run migrations on startup, then start uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn soas_backend.main:app --host 0.0.0.0 --port 8000"]
