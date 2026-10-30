#!/bin/sh
# An explicitly local database prevents accidental imports into hosted PostgreSQL.
set -eu
cd "$(dirname "$0")/.."
document_dev_dir="$PWD/.document-dev.local"
document_dev_port="${OPTISPACE_DEV_PORT:-8001}"
# Explain an occupied port before touching the database; never stop another server.
venv/bin/python - "$document_dev_port" <<'PORTCHECK'
import socket
import sys

try:
    port = int(sys.argv[1])
    if not 1024 <= port <= 65535:
        raise ValueError
except ValueError:
    sys.exit("OPTISPACE_DEV_PORT must be a number between 1024 and 65535.")
with socket.socket() as connection:
    connection.settimeout(1)
    if connection.connect_ex(("127.0.0.1", port)) == 0:
        sys.exit(
            f"Port {port} is already in use. If the app is running, open http://127.0.0.1:{port}/. "
            "To load code changes, stop that server with Ctrl+C in its terminal, then run this command again. "
            "Or choose another port: OPTISPACE_DEV_PORT=8002 sh scripts/run-document-dev.sh"
        )
PORTCHECK
document_pg_bin="${OPTISPACE_PG_BIN:-/usr/lib/postgresql/18/bin}"
if [ ! -f "$document_dev_dir/pg/PG_VERSION" ]; then
    echo 'The isolated database is not initialized. See docs/timetable-import.md.' >&2
    exit 1
fi
if ! "$document_pg_bin/pg_ctl" -D "$document_dev_dir/pg" status >/dev/null 2>&1; then
    "$document_pg_bin/pg_ctl" -D "$document_dev_dir/pg" \
        -l "$document_dev_dir/postgres.log" \
        -o "-h 127.0.0.1 -p 55439 -k $document_dev_dir" start
fi
export DATABASE_URL='postgresql://optispace_local@127.0.0.1:55439/optispace_document_dev?sslmode=disable'
export DJANGO_DEBUG=true
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
export OPTISPACE_IMAGE_MODEL="$document_dev_dir/ocr-models/english.onnx"
if [ ! -f "$OPTISPACE_IMAGE_MODEL" ]; then
    venv/bin/python scripts/install-image-model.py --directory "$document_dev_dir/ocr-models"
fi
if [ -x "$document_dev_dir/ocr/usr/bin/tesseract" ]; then
    export TESSERACT_CMD="$document_dev_dir/ocr/usr/bin/tesseract"
    export TESSDATA_PREFIX="$document_dev_dir/ocr/usr/share/tesseract-ocr/5/tessdata"
    export LD_LIBRARY_PATH="$document_dev_dir/ocr/usr/lib/x86_64-linux-gnu"
fi
venv/bin/python backend/manage.py migrate --noinput
echo "Local development app: http://127.0.0.1:$document_dev_port/"
exec venv/bin/python backend/manage.py runserver "127.0.0.1:$document_dev_port" --noreload
