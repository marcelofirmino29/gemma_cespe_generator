# config/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv # Importar load_dotenv
from django.core.exceptions import ImproperlyConfigured # Para erros de config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Carregar variáveis do .env localizado na BASE_DIR
dotenv_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=dotenv_path)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/stable/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-fallback-key-change-me') # Use variável de ambiente ou gere uma nova

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True' # Ler do .env ou padrão True

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')


# --- Configurações da IA ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") # Busca a variável chamada GOOGLE_API_KEY
AI_MODEL_NAME = 'gemini-1.5-flash-latest' # Ou outro modelo Gemma/Gemini disponível
AI_GENERATION_TEMPERATURE = 0.7 # Ajuste conforme necessário
AI_MAX_QUESTIONS_PER_REQUEST = 150 # Reduzido para testes iniciais mais rápidos

# === INÍCIO DA ADIÇÃO ===
# Configurações de Segurança para a API Google AI (Usando Strings)
# O serviço QuestionGenerationService precisará converter estas strings para os Enums da API.
# Thresholds possíveis (strings): "BLOCK_NONE", "BLOCK_ONLY_HIGH", "BLOCK_MEDIUM_AND_ABOVE", "BLOCK_LOW_AND_ABOVE"
# Veja a documentação oficial do Google AI para detalhes sobre cada categoria e threshold.
GOOGLE_AI_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT",       "threshold": "BLOCK_NONE"}, # Menos restritivo
    {"category": "HARM_CATEGORY_HATE_SPEECH",      "threshold": "BLOCK_NONE"}, # Menos restritivo
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT","threshold": "BLOCK_NONE"}, # Menos restritivo
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT","threshold": "BLOCK_NONE"}, # Menos restritivo
    # Ajuste os valores de "threshold" conforme sua necessidade de segurança.
    # "BLOCK_MEDIUM_AND_ABOVE" é um ponto de partida mais seguro que "BLOCK_NONE".
]
# === FIM DA ADIÇÃO ===

# Verifica se a chave da API foi carregada (ESSENCIAL)
if not GOOGLE_API_KEY:
    if not DEBUG:
         raise ImproperlyConfigured("FATAL: GOOGLE_API_KEY não definida nas variáveis de ambiente (.env).")
    else:
         print("\n\n******************************************************")
         print("AVISO: GOOGLE_API_KEY não definida. A geração de questões falhará.")
         print("Crie um arquivo .env na raiz do projeto com GOOGLE_API_KEY=SUA_CHAVE")
         print("******************************************************\n\n")


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Nosso App:
    'generator',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls' # Aponta para o urls.py principal em config/

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    # ...
]


# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Boa_Vista' # Fuso horário correto para Boa Vista
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
# STATIC_ROOT = BASE_DIR / 'staticfiles' # Descomente para produção se necessário

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# settings.py  (Adicione ou modifique esta variável)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': { # Opcional: Define como as mensagens serão formatadas
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',  # <<< Nível mínimo que este handler processa
            'class': 'logging.StreamHandler', # Envia para o terminal
            'formatter': 'simple' # Escolha 'simple' ou 'verbose'
        },
        # Você pode adicionar outros handlers aqui (ex: para arquivos)
    },
    'loggers': {
        'django': { # Configura logs internos do Django
            'handlers': ['console'],
            'level': 'INFO', # Geralmente INFO é suficiente para o Django
            'propagate': False,
        },
        'generator': { # Logger específico do seu app (IMPORTANTE)
            'handlers': ['console'],
            'level': 'DEBUG',  # <<< Nível mínimo que este logger captura
            'propagate': False, # Evita duplicar mensagens se o raiz também logar
        },
        # Se você não quiser configurar 'generator' especificamente, pode
        # configurar o logger raiz '' para DEBUG:
        # '': {
        #     'handlers': ['console'],
        #     'level': 'DEBUG',
        #     'propagate': True,
        # },
    },
}