#!/bin/bash
set -e

cd /app
source /dispatcharrpy/bin/activate

# Wait for Django secret key
echo 'Waiting for Django secret key...'
while [ ! -f /data/jwt ]; do sleep 1; done
export DJANGO_SECRET_KEY="$(tr -d '\r\n' < /data/jwt)"

# Wait for migrations to complete (check that command succeeds AND no unapplied migrations remain)
echo 'Waiting for migrations to complete...'
until python manage.py showmigrations > /tmp/mig_status 2>&1 && ! grep -q '\[ \]' /tmp/mig_status; do
    echo 'Migrations not ready yet (or DB unavailable), waiting...'
    if [ -f /tmp/mig_status ]; then
        # Print last line of error for visibility without spamming
        tail -n 1 /tmp/mig_status
    fi
    sleep 5
done
rm -f /tmp/mig_status

# Start Celery
echo 'Migrations complete, starting Celery...'
celery -A dispatcharr beat -l info &

# Default to nice level 5 (lower priority) - safe for unprivileged containers
# Negative values require SYS_NICE capability
NICE_LEVEL="${CELERY_NICE_LEVEL:-5}"
if [ "$NICE_LEVEL" -lt 0 ] 2>/dev/null; then
    echo "Warning: CELERY_NICE_LEVEL=$NICE_LEVEL is negative, requires SYS_NICE capability"
fi
nice -n "$NICE_LEVEL" celery -A dispatcharr worker -l info --autoscale=6,1
