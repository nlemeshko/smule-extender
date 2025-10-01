# syntax=docker/dockerfile:1
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Установка Python и ADB
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip adb ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .
