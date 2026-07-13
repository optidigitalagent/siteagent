# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-telegram.txt .
RUN pip install --no-cache-dir -r requirements-telegram.txt

COPY . .

CMD ["python", "-m", "site_agent.telegram_bot"]
