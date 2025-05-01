# Use uma imagem base oficial do Python
FROM python:3.11-slim

# Defina variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Crie e defina o diretório de trabalho
WORKDIR /app

# Instale dependências do sistema (se necessário, ex: para psycopg2)
# RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client libpq-dev gcc && rm -rf /var/lib/apt/lists/*
# Para MySQL:
# RUN apt-get update && apt-get install -y --no-install-recommends default-libmysqlclient-dev build-essential && rm -rf /var/lib/apt/lists/*


# Instale dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie o código da aplicação
COPY . .

# Colete arquivos estáticos (se usar Whitenoise ou Cloud Storage gerenciado no build)
# Certifique-se que DJANGO_SETTINGS_MODULE está definido ou use --settings
# RUN python manage.py collectstatic --noinput --clear
# É mais seguro definir variáveis de ambiente aqui se necessário para collectstatic
# ARG DJANGO_SETTINGS_MODULE=seu_projeto.settings.production
# ENV DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE}
RUN python manage.py collectstatic --noinput

# Exponha a porta que o Gunicorn vai usar (Cloud Run espera 8080 por padrão)
EXPOSE 8080

# Comando para rodar a aplicação usando Gunicorn
# Substitua 'seu_projeto.wsgi' pelo caminho correto do seu arquivo wsgi.py
# O número de workers é ajustado automaticamente pelo Gunicorn baseado nos cores,
# mas você pode ajustar se necessário. Cloud Run gerencia o scaling de instâncias.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "seu_projeto.wsgi:application"]