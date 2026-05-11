FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/backend

COPY pyproject.toml /app/backend/pyproject.toml
COPY app /app/backend/app
COPY alembic /app/backend/alembic
COPY alembic.ini /app/backend/alembic.ini

RUN pip install --no-cache-dir --upgrade pip setuptools && pip install --no-cache-dir -e .

EXPOSE 8000

COPY entrypoint.sh /app/backend/entrypoint.sh
RUN chmod +x /app/backend/entrypoint.sh

CMD ["/app/backend/entrypoint.sh"]
