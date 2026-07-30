FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN addgroup --system smoke \
    && adduser --system --ingroup smoke smoke

COPY --chown=smoke:smoke scripts/smoke-production.py /usr/local/bin/date-planner-smoke

USER smoke

ENTRYPOINT ["python", "/usr/local/bin/date-planner-smoke"]
CMD ["--help"]
