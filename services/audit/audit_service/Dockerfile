FROM python:3.11-slim

# Prevent Python from buffering stdout/stderr (crucial for Docker logs)
ENV PYTHONUNBUFFERED=1
# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies for Psycopg2 (Postgres driver)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]