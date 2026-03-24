FROM python:3.11-slim

# Install SQL Server ODBC Driver 18 (Debian 12/bookworm)
RUN set -eux; \
  apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg apt-transport-https \
    unixodbc unixodbc-dev \
  && mkdir -p /usr/share/keyrings \
  && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
     | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
  && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
     > /etc/apt/sources.list.d/microsoft-prod.list \
  && apt-get update \
  && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 mssql-tools18 \
  && rm -rf /var/lib/apt/lists/*

# OS deps often needed by ML libs & SQL Server client libs (adjust if unneeded)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ git curl \
    unixodbc-dev libgomp1 \
    awscli \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching
COPY requirements.txt .

ARG PIP_INDEX_URL_CPU=https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --extra-index-url ${PIP_INDEX_URL_CPU} -r requirements.txt


# Copy app
COPY . .

ENV PYTHONPATH="/app:/app/error_handling_system"

# Env for vectors/config
ENV APP_BUCKET=self-healing-system
ENV VECTOR_DIR=/mnt/vectors
ENV PORT=3978

# Bootstrap: sync vectors/prompts/configs from S3, then start Flask webhook
# (safe even if paths are empty in S3)
COPY <<'BASH' /app/entrypoint.sh
#!/usr/bin/env bash
set -euo pipefail
mkdir -p "${VECTOR_DIR}"
aws s3 sync "s3://${APP_BUCKET}/vector_store/" "${VECTOR_DIR}/" || true
aws s3 sync "s3://${APP_BUCKET}/prompts/" "/app/prompts/" || true
aws s3 sync "s3://${APP_BUCKET}/config/" "/app/config/" || true
exec python scripts/run_outgoing_webhook.py
BASH
RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
