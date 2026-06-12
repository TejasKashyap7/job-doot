FROM python:3.11-slim

WORKDIR /app

# Tectonic (LaTeX compiler) — fetched fresh; small static binary, works on amd64 + arm64
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl wget \
    && rm -rf /var/lib/apt/lists/*

RUN ARCH=$(uname -m) \
    && case "$ARCH" in \
         x86_64) TECTONIC_ARCH=x86_64-unknown-linux-musl ;; \
         aarch64) TECTONIC_ARCH=aarch64-unknown-linux-musl ;; \
         *) echo "Unsupported arch $ARCH" && exit 1 ;; \
       esac \
    && curl -fsSL "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-${TECTONIC_ARCH}.tar.gz" \
       | tar -xz -C /usr/local/bin tectonic \
    && chmod +x /usr/local/bin/tectonic

# Build context is project root (see docker-compose.yml), so paths are
# relative to repo root.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/ /app/backend/
WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
