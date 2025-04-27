FROM python:3.12-alpine

ENV PYTHONUNBUFFERED 1

# --- Superuser Credentials ---
# Define build arguments for credentials. These MUST be passed during build.
# Defaulting to empty strings is just a placeholder.
ARG SU_USERNAME=""
ARG SU_EMAIL=""
ARG SU_PASSWORD=""

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
RUN python manage.py migrate

# --- Create Superuser ---
# Uses the build arguments passed via --build-arg
# The --noinput flag tells createsuperuser to use environment variables.
# IMPORTANT: This runs during the IMAGE BUILD. Consider security implications.
RUN echo "Attempting to create superuser '${SU_USERNAME}'..." && \
    export DJANGO_SUPERUSER_USERNAME=${SU_USERNAME} && \
    export DJANGO_SUPERUSER_EMAIL=${SU_EMAIL} && \
    export DJANGO_SUPERUSER_PASSWORD=${SU_PASSWORD} && \
    python manage.py createsuperuser --noinput || \
    echo "Superuser already exists or DB not ready/accessible during build, continuing..."

# --- Default Runtime Command ---
CMD ["python", "manage.py", "runserver", "0.0.0.0:80"]