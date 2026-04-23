FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data

EXPOSE 80

ENV PYTHONUNBUFFERED=1
ENV PORT=80

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-80}"]
