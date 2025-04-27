# Dockerfile para Aplicação Django (Plataforma Especificada)

# --- Estágio Builder (Opcional, mas bom para compilar dependências) ---
FROM --platform=linux/amd64 python:3.12-slim as builder

WORKDIR /wheels_build

# Instala dependências de build se necessário
# RUN apt-get update && apt-get install -y build-essential ...

COPY requirements.txt .
# Baixa as dependências como wheels
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# --- Estágio Final ---
FROM --platform=linux/amd64 python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Copia as dependências pré-compiladas
COPY --from=builder /wheels /wheels

# Instala as dependências a partir dos wheels locais
RUN pip install --no-cache-dir /wheels/*

# Copia o restante do código da aplicação
COPY . .

# Coleta arquivos estáticos (se usar WhiteNoise)
# Descomente e ajuste se necessário
# RUN python manage.py collectstatic --noinput

# <<< REMOVIDO: RUN python manage.py migrate >>>
# As migrações devem ser executadas durante o deploy ou como um Job separado.

# Expõe a porta
EXPOSE 8000

# Comando para rodar a aplicação (Gunicorn/WSGI)
# Verifique se 'gemma_cespe_generator.wsgi:application' é o caminho correto
CMD ["gunicorn", "--bind", "0.0.0.0:80", "gemma_cespe_generator.wsgi:application"]

# Exemplo alternativo usando Uvicorn para ASGI
# CMD ["uvicorn", "gemma_cespe_generator.asgi:application", "--host", "0.0.0.0", "--port", "8000"]