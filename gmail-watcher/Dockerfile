FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Reuse the project's pinned deps so versions match the backend.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY gmail-watcher/ /app/

ENV PYTHONUNBUFFERED=1

CMD ["python", "watcher.py"]
