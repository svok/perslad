FROM python:3.12-slim

WORKDIR /app

# Добавляем текущую директорию в PYTHONPATH для корректных импортов
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Копируем requirements.txt и устанавливаем зависимости
COPY metrics_loader/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Монтируем код через volumes (не копируем в образ)
# Код будет доступен по пути /app/metrics_loader

CMD ["python", "metrics_loader/main.py"]
