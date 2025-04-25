# =========================================================================
# Fase 1: Build (se necessário para dependências complexas, não usado aqui)
# =========================================================================
# (Poderia ter uma fase de build para compilar assets JS/CSS se você usasse Node)

# =========================================================================
# Fase 2: Runtime Final
# =========================================================================
# Use a imagem oficial do Python 3.12 na versão 'slim' para um tamanho menor
FROM python:3.12-slim

# Defina variáveis de ambiente úteis
ENV PYTHONDONTWRITEBYTECODE 1  # Impede o Python de criar arquivos .pyc
ENV PYTHONUNBUFFERED 1      # Garante que os logs do Python saiam direto para o console/logs do container
ENV APP_HOME=/app           # Define o diretório da aplicação

# Crie o diretório da aplicação
WORKDIR $APP_HOME

# Instale dependências do sistema necessárias
# - build-essential: Pode ser necessário para compilar algumas bibliotecas Python.
# - libpq-dev: Necessário para compilar o psycopg2 (driver do PostgreSQL) se não usar a versão -binary.
# --no-install-recommends: Evita instalar pacotes recomendados que podem não ser necessários.
# Limpe o cache do apt para reduzir o tamanho da imagem.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copie APENAS o arquivo de dependências primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instale as dependências Python
# --no-cache-dir: Desativa o cache do pip para reduzir o tamanho da imagem.
RUN pip install --no-cache-dir -r requirements.txt

# Crie um usuário e grupo não-root para rodar a aplicação (MELHOR PRÁTICA DE SEGURANÇA)
RUN addgroup --system app && adduser --system --ingroup app app

# Copie o restante do código da aplicação para o diretório de trabalho
COPY . .

# Mude a propriedade dos arquivos da aplicação para o usuário não-root
RUN chown -R app:app $APP_HOME

# Execute collectstatic como root (geralmente mais simples que ajustar permissões para o usuário 'app')
# --noinput: Não pede confirmação.
# --clear: Limpa o diretório STATIC_ROOT antes de copiar os novos arquivos.
# Certifique-se que STATIC_ROOT está definido corretamente em settings.py.
RUN python manage.py collectstatic --noinput --clear

# Mude para o usuário não-root
USER app

# A porta real será definida pela variável de ambiente PORT injetada pelo Cloud Run.
# EXPOSE 8080 # Documenta a porta padrão que poderia ser usada, mas não é estritamente necessária aqui.

# Comando para iniciar a aplicação usando Gunicorn
# - exec: Garante que Gunicorn seja o processo principal (PID 1) e receba sinais corretamente.
# - --bind 0.0.0.0:$PORT: Liga o Gunicorn a todas as interfaces de rede na porta fornecida pela variável de ambiente PORT (padrão 8080 no Cloud Run).
# - --workers: Número de processos worker (ajuste conforme CPU/memória disponíveis). Comece com 2-4.
# - --threads: Número de threads por worker (útil para I/O bound como Django com worker gthread).
# - --worker-class=gthread: Worker baseado em threads, bom para Django.
# - meuprojeto.wsgi:application: Caminho para o objeto de aplicação WSGI do seu projeto Django (ajuste 'meuprojeto' para o nome real do seu projeto).
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --worker-class=gthread meuprojeto.wsgi:application
