#!/bin/sh
set -e

# Wait for the database to become reachable.
until python -c "import socket,sys; s=socket.socket(); s.settimeout(2); s.connect(('db',5432)); s.close()" 2>/dev/null; do
    echo "Waiting for database..."
    sleep 2
done

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py ensure_superuser

exec "$@"
