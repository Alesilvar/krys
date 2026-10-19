#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
  echo "Falta el entorno de Python .venv. Instala primero las dependencias de requirements.txt."
  exit 1
fi

docker compose up -d db
.venv/bin/python manage.py migrate --noinput
exec .venv/bin/python manage.py runserver 127.0.0.1:8000
