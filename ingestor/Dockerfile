FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# системные зависимости (минимум)
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Устанавливаем fsnotify system library (опционально)
RUN apt-get update && apt-get install -y \
    libinotify-tools \
 && rm -rf /var/lib/apt/lists/*

# код (может быть заменён volume mount)
COPY infra/ ./infra/
COPY ingestor/ ./ingestor/
RUN pip install --no-cache-dir -r ./ingestor/requirements.txt

# default entrypoint
CMD ["python", "-m", "ingestor.app.main"]
