FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONFAULTHANDLER=1

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    docker.io \
    curl \
    && rm -rf /var/lib/apt/lists/*


COPY servers/ ./servers/
RUN pip install --no-cache-dir -r servers/requirements.txt

# Если зависимость не та или версии конфликтуют, эта команда упадет и остановит сборку.
RUN python -c "import mcp; import sse_starlette; import uvicorn; import aiomysql; import pydantic; print('✅ MCP dependencies validated successfully')"

CMD ["python", "-m", "servers.mcp_bash"]
