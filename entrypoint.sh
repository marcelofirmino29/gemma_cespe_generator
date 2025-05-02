#!/bin/sh

# Aplica as migrações
python manage.py migrate --noinput

# Coleta arquivos estáticos (opcional)
# python manage.py collectstatic --noinput

# Inicia o servidor
exec gunicorn myproject.wsgi:application --bind 0.0.0.0:8000
