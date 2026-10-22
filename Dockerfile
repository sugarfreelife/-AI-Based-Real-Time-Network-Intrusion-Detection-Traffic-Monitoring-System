FROM python:3.12.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements-dev.lock ./requirements-dev.lock
RUN python -m pip install --no-cache-dir --requirement requirements-dev.lock \
    && addgroup --system nids \
    && adduser --system --ingroup nids --home /nonexistent nids

COPY alembic.ini pyproject.toml README.md ./
COPY backend ./backend
COPY database ./database
COPY ml ./ml
COPY nids_engine ./nids_engine
COPY docker/monitor-entrypoint.sh /usr/local/bin/nids-monitor-container
RUN chmod 0755 /usr/local/bin/nids-monitor-container

USER nids
EXPOSE 8000
CMD ["python", "-m", "backend.app.cli", "--host", "0.0.0.0", "--port", "8000"]
