FROM python:3.11-slim

# Установка зависимостей
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .