# Family Care Circle web app, MOCK backend only (no model file, no torch, no llama-cpp-python).
# Build from the REPOSITORY ROOT:  docker build -f deploy/Dockerfile -t fcc-demo .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_BACKEND=mock \
    APP_DB_PATH=/data/familycare.sqlite3 \
    APP_JOB_ISOLATION=thread

WORKDIR /srv/fcc

# Dependencies first (cached layer): the app's pins plus the five packages the mock pipeline imports.
COPY requirements-app.txt deploy/requirements-deploy.txt ./
RUN pip install -r requirements-app.txt -r requirements-deploy.txt

# The app, the research code it calls, its config, and the small synthetic notes used by app.dev_seed.
COPY app ./app
COPY src ./src
COPY config.yaml ./config.yaml
COPY data/raw ./data/raw

# Non-root user; /data is the only writable place (the app also creates the database file as 0600).
RUN useradd --uid 10001 --no-log-init --home-dir /srv/fcc fcc \
    && mkdir -p /data \
    && chown -R fcc:fcc /data
USER fcc
VOLUME ["/data"]

# Render sets $PORT (default 10000). ONE worker on purpose: the job queue and the login throttle live in memory.
EXPOSE 10000
CMD ["sh", "-c", "exec python -m uvicorn app.web.main:create_app --factory --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --no-server-header"]
