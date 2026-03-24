FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY . /app
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh
RUN useradd -m appuser && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["sh", "-c", "gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker --workers ${GUNICORN_WORKERS:-2} --bind 0.0.0.0:${PORT:-8000} --timeout ${GUNICORN_TIMEOUT:-60} --keep-alive 5 --access-logfile - --error-logfile -"]
