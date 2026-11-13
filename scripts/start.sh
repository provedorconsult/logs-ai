#!/bin/sh
set -eu
python -m logs_ai.migrate
exec uvicorn logs_ai.main:app --host 0.0.0.0 --port 8000 --no-access-log
