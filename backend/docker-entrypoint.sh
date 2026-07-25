#!/bin/sh
# Backend container entrypoint.
# API (uvicorn) runs migrations before serving; workers skip this.
set -e

case "$1" in
  uvicorn)
    if [ "${SKIP_MIGRATE:-0}" != "1" ]; then
      echo "[entrypoint] alembic upgrade head ..."
      alembic upgrade head
      echo "[entrypoint] migrations done"
    fi
    ;;
esac

exec "$@"
