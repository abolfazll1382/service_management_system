"""Gunicorn settings (``gunicorn config.wsgi:application -c gunicorn.conf.py``).

Everything tunable is an environment variable, so one image runs anywhere.

Capacity note: every worker thread holds its own database connection (Django connections are
per-thread), so one container can open up to ``WEB_CONCURRENCY × GUNICORN_THREADS`` PostgreSQL
connections (18 with the defaults on a 4-core machine). Keep that, times the number of replicas,
below the server's ``max_connections``.
"""

from __future__ import annotations

import multiprocessing
import os


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")  # all interfaces: container-only

workers = _int("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 9))
threads = _int("GUNICORN_THREADS", 2)
worker_class = "gthread"

# A request that outlives this is killed. Keep it above DB_STATEMENT_TIMEOUT_MS (30 s by default)
# so a slow query fails with a clean error before the worker is reaped.
timeout = _int("GUNICORN_TIMEOUT", 45)
graceful_timeout = _int("GUNICORN_GRACEFUL_TIMEOUT", 30)
keepalive = _int("GUNICORN_KEEPALIVE", 5)

# Recycle workers now and then (with jitter so they do not all restart together).
max_requests = _int("GUNICORN_MAX_REQUESTS", 2000)
max_requests_jitter = _int("GUNICORN_MAX_REQUESTS_JITTER", 200)

# Heartbeat files in RAM: the usual fix for "worker timeout" under Docker's overlay filesystem.
worker_tmp_dir = "/dev/shm"  # noqa: S108

# Cheap, early rejection of absurd requests (the app also caps the body at API_MAX_BODY_BYTES).
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Which peers may set X-Forwarded-* headers. Only list the address(es) of YOUR reverse proxy;
# "*" is acceptable only when the container is reachable from the proxy alone.
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")

# Logs go to stdout/stderr for the platform to collect. The access log records the URL *path*
# only: the queue's `search` parameter may carry a national ID or phone number, which must not end
# up in log files. The request id ties a line to the application's own log entries.
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s "%(m)s %(U)s" %(s)s %(b)s %(L)ss "%({x-request-id}o)s"'
