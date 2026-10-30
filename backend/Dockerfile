# syntax=docker/dockerfile:1.7
#
# Two stages: the first builds the virtualenv, the second contains only that venv and the code
# (no pip cache, no build tools), runs as an unprivileged user and has a health check.
#
#   docker build -t citizen-services-api .
#   docker run --rm -p 8000:8000 --env-file .env citizen-services-api

ARG PYTHON_VERSION=3.13

# ---- build: resolve and install the pinned dependencies -----------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /build
COPY requirements.txt .
# Binary wheels only (psycopg[binary], argon2-cffi): nothing is compiled, so no compiler is needed.
RUN pip install --only-binary=:all: -r requirements.txt

# ---- runtime ------------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}" \
    DJANGO_SETTINGS_MODULE=config.settings.production

# Fixed numeric ids so volume permissions and Kubernetes `runAsUser` are predictable.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=root:root . /app
RUN chmod 0755 /app/entrypoint.sh

USER 10001:10001
EXPOSE 8000

# Liveness *and* database reachability (the view answers 503 when PostgreSQL is down). The slim
# image has no curl, so the check uses the interpreter that is already there.
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=4).status == 200 else 1)"]

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--config", "gunicorn.conf.py"]
