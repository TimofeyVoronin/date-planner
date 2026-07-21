FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
RUN python -m pip install --upgrade pip \
    && python -m pip install ".[dev]"

COPY . .
RUN chmod +x /app/scripts/start.sh

EXPOSE 8000

CMD ["sh", "/app/scripts/start.sh"]
