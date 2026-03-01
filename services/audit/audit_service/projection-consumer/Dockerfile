FROM python:3.11-slim
 
WORKDIR /app
 
# Install librdkafka system dependency (required by confluent-kafka)
RUN apt-get update && apt-get install -y \
    librdkafka-dev gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*
 
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
# Copy consumer source files
COPY consumer.py deserialise.py project.py django_setup.py ./
 
# Mount the Django source so we can import audit_read.models and
# config.settings without duplicating the Django app
# (handled by volume mount in docker-compose.yml)
 
CMD ["python", "-u", "consumer.py"]
