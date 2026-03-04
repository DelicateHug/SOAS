FROM python:3.12-slim

WORKDIR /app

# Install git (needed for git sync feature)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Install shared package
COPY shared/ /tmp/shared/
RUN pip install --no-cache-dir /tmp/shared/ && rm -rf /tmp/shared/

# Install VisualPython core modules (headless - no PyQt6)
# Only copy the pure-Python modules needed for compilation
COPY VisualPython/src/visualpython/compiler/ /opt/vp/visualpython/compiler/
COPY VisualPython/src/visualpython/serialization/ /opt/vp/visualpython/serialization/
COPY VisualPython/src/visualpython/nodes/models/ /opt/vp/visualpython/nodes/models/
COPY VisualPython/src/visualpython/nodes/__init__.py /opt/vp/visualpython/nodes/__init__.py
COPY VisualPython/src/visualpython/nodes/registry.py /opt/vp/visualpython/nodes/registry.py
COPY VisualPython/src/visualpython/graph/ /opt/vp/visualpython/graph/
COPY VisualPython/src/visualpython/variables/ /opt/vp/visualpython/variables/
COPY VisualPython/src/visualpython/utils/ /opt/vp/visualpython/utils/
COPY VisualPython/src/visualpython/__init__.py /opt/vp/visualpython/__init__.py

# Install VisualPython2 headless modules
COPY VisualPython2/src/visualpython2/ /opt/vp2/visualpython2/

ENV PYTHONPATH="/opt/vp:/opt/vp2:${PYTHONPATH}"

# Install backend package (needed by git sync task)
COPY backend/pyproject.toml /tmp/backend/pyproject.toml
COPY backend/src/ /tmp/backend/src/
COPY backend/alembic.ini /tmp/backend/alembic.ini
COPY backend/alembic/ /tmp/backend/alembic/
RUN pip install --no-cache-dir /tmp/backend/ && rm -rf /tmp/backend/

# Copy worker source + config (setuptools needs src/ to resolve packages)
COPY workers/pyproject.toml ./
COPY workers/src/ ./src/

# Install worker package + dependencies
RUN pip install --no-cache-dir .

ENV PYTHONPATH="/app/src:/opt/vp:/opt/vp2"

# Create automations directory (will be mounted as volume)
RUN mkdir -p /app/automations /tmp/sandbox

CMD ["celery", "-A", "soas_workers.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
