#!/bin/bash

set -e

echo "⏳ Waiting for MySQL to be ready..."
until python -c "
import os, MySQLdb
try:
    MySQLdb.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        passwd=os.getenv('DB_PASSWORD'),
        db=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306))
    )
    print('✅ MySQL is ready!')
    exit(0)
except Exception as e:
    print(f'⏳ MySQL not ready: {e}')
    exit(1)
"; do
    sleep 2
done

echo "📦 Running migrations..."
python manage.py migrate --noinput

echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

echo "🚀 Starting Gunicorn..."
exec gunicorn meesho_generator.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --worker-class gthread \
    --threads 2 \
    --log-level info