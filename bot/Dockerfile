FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . .

# Установить PYTHONPATH
ENV PYTHONPATH=/app

# Запуск бота
CMD ["python", "-m", "app.main"]