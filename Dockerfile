# Базовый образ с Python
FROM python:3.12-slim

# Установка зависимостей для сборки psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Установка рабочей директории
WORKDIR /app

# Копирование файла зависимостей
COPY requirements.txt .

# Установка зависимостей Python
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY backend/ ./backend/
COPY templates/ ./templates/
COPY alembic/ ./alembic/
COPY tests/ ./tests/
COPY alembic.ini .

# Указание порта
EXPOSE 8000

# Команда для запуска приложения
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.routs:app --host 0.0.0.0 --port 8000"]