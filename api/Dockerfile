FROM python:3.11-slim

# критично для старых CPU на VPS
ENV NPY_DISABLE_CPU_FEATURES=AVX512F,AVX2,FMA

WORKDIR /app

# ✅ Установка curl для healthcheck
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# сначала зависимости
COPY requirements.txt .

# фикс numpy под слабые CPU
RUN pip install --no-cache-dir numpy==1.26.4

# остальные зависимости
RUN pip install --no-cache-dir -r requirements.txt

# код приложения
COPY . .

# запуск API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]