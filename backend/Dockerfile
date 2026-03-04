FROM python:3.12-slim

WORKDIR /app

# Install git (needed for git sync feature)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

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
