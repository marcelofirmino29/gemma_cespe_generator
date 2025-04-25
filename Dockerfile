# Dockerfile para Aplicação Django (Plataforma Especificada)

# --- Estágio Builder (Opcional, mas bom para compilar dependências) ---
# <<< Adicionado --platform >>>
FROM --platform=linux/amd64 python:3.12-slim as builder

WORKDIR /wheels_build

# Instala dependências de build se necessário (ex: para compilar pacotes C)
# RUN apt-get update && apt-get install -y build-essential ...

COPY requirements.txt .
# Baixa as dependências como wheels (para a plataforma especificada)
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# --- Estágio Final ---
# <<< Adicionado --platform >>>
FROM --platform=linux/amd64 python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Copia as dependências pré-compiladas como wheels do estágio builder
COPY --from=builder /wheels /wheels

# Instala as dependências a partir dos wheels locais
# Garante que está instalando para a mesma plataforma linux/amd64
RUN pip install --no-cache /wheels/*

# Copia o restante do código da aplicação
COPY . .

# Coleta arquivos estáticos (se usar WhiteNoise)
# Descomente e ajuste se necessário
# RUN python manage.py collectstatic --noinput

# Expõe a porta
EXPOSE 8000

# Comando para rodar a aplicação (Gunicorn/WSGI)
# Verifique se 'docling_django.wsgi:application' é o caminho correto
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "docling_django.wsgi:application"]

# Exemplo alternativo usando Uvicorn para ASGI
# CMD ["uvicorn", "docling_django.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
