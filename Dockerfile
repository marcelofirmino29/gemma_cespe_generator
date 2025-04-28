# Usa uma imagem base Python 3.12 slim (Alpine pode ter problemas com algumas libs C)
# Especifica a plataforma para compatibilidade
FROM --platform=linux/amd64 python:3.12-slim

# Define variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Instala dependências do sistema ANTES de copiar código
# Adiciona build-base e postgresql-dev para compilar psycopg2 se necessário
# Remove após instalar para manter imagem menor
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
# Usar /app é uma convenção comum, mas /generator também funciona
WORKDIR /app

# Copia e instala dependências Python
# Atualiza pip e instala do requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Coleta arquivos estáticos (IMPORTANTE se usar WhiteNoise)
# Certifique-se que STATIC_ROOT está definido em settings.py
# RUN python manage.py collectstatic --noinput --clear

# <<< REMOVIDO: RUN python manage.py migrate >>>
# As migrações devem ser executadas no ambiente de deploy.

# Expõe a porta que o Gunicorn usará
EXPOSE 8000

# --- Comando para rodar a aplicação em produção com Gunicorn ---
# Usa a porta definida pela variável de ambiente PORT (padrão Cloud Run é 8080)
# ou 8000 como fallback.
# Ajuste 'gemma_cespe_generator.wsgi:application' se o nome do seu projeto/wsgi for diferente.
CMD ["gunicorn", "--bind", "0.0.0.0:${PORT:-8000}", "--workers", "2", "gemma_cespe_generator.wsgi:application"]