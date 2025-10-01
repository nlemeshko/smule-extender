# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Установка только ADB (Python уже есть в базе)
RUN apt-get update && apt-get install -y --no-install-recommends \
    adb ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Запуск: можно передать адрес через ADB_DEVICE или флаг --device
# Примеры:
#   docker run --net=host -e ADB_DEVICE=192.168.2.105:5555 smule-extender
#   docker run --net=host smule-extender python main.py --device 192.168.2.105:5555
CMD ["python", "main.py"]
