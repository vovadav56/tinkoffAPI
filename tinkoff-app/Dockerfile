FROM python:3.11-slim

WORKDIR /app

# Установка клиента MySQL
RUN apt-get update && apt-get install -y default-mysql-client && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY TinApyProject.py .
COPY entrypoint.sh .

ENTRYPOINT ["bash", "entrypoint.sh"]
