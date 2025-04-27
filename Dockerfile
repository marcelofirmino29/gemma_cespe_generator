FROM python:3.12-alpine

ENV PYTHONUNBUFFERED 1

# --- System Dependencies ---
# Instala dependências do sistema
RUN apk add --no-cache gcc musl-dev libffi-dev python3-dev build-base postgresql-dev

WORKDIR /generator

# --- Python Dependencies ---
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# --- Application Code ---
COPY . .

# --- Database Migrations ---
# Executa as migrations antes de criar o superuser ou iniciar o servidor
# RUN python manage.py migrate

# --- Default Runtime Command ---
CMD ["python", "manage.py", "runserver", "0.0.0.0:80"]