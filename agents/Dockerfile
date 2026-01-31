FROM python:3.12-slim

WORKDIR /app

# Добавляем текущую директорию в PYTHONPATH для корректных импортов
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONFAULTHANDLER=1

COPY infra/ ./infra/
COPY agents/ ./agents/

RUN pip install --no-cache-dir -r agents/requirements.txt

# === ТЕСТ СБОРКИ (BUILD TESTING) ===
RUN python -c "import langgraph; import langchain; import mcp; import httpx; print('✅ Agent dependencies validated successfully')"

# Замените CMD на:
CMD ["python", "-m", "uvicorn", "agents.main:app", "--host", "0.0.0.0", "--port", "8123", "--log-level", "info", "--no-access-log"]
