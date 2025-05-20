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
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-fallback-key-change-me')

DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True' # Permite configurar DEBUG via .env

#ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')
# Ajuste ALLOWED_HOSTS conforme suas necessidades de desenvolvimento e produção.
# O '*' é inseguro para produção.
ALLOWED_HOSTS = ['http://35.209.77.3/','https://generator-v1-2-754311810435.us-central1.run.app','.vercel.app']
if DEBUG:
    ALLOWED_HOSTS.extend(['127.0.0.1', 'localhost'])
else:
    # Para produção, seja mais específico. O '*' abaixo é um placeholder se você não tiver outros hosts definidos.
    # Considere remover '*' se não for necessário, ou defina via variável de ambiente.
    ALLOWED_HOSTS.append(os.getenv('DJANGO_PRODUCTION_HOST', '*'))


CSRF_TRUSTED_ORIGINS = [
    'https://generator-v1-2-754311810435.us-central1.run.app',
    # Adicione 'http://127.0.0.1:8000' e 'http://localhost:8000' se estiver testando localmente com DEBUG=False
]
if DEBUG:
    CSRF_TRUSTED_ORIGINS.extend(['http://127.0.0.1:8000', 'http://localhost:8000'])


# --- Configurações da IA (Agora para Ollama) ---
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL_NAME = os.getenv('OLLAMA_MODEL_NAME', 'gemma3:4b-it-qat') # Ex: 'gemma:latest', 'gemma:7b'
# OLLAMA_REQUEST_TIMEOUT = float(os.getenv('OLLAMA_REQUEST_TIMEOUT', 3000.0)) # Timeout em segundos

# As configurações antigas do Google AI podem ser mantidas se outra parte do seu sistema ainda as utiliza,
# mas o QuestionGenerationService (após a refatoração para Ollama) não as usará mais diretamente.
# Se você não as usa em mais nenhum lugar, pode comentá-las ou removê-las.
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# AI_MODEL_NAME_GOOGLE = 'gemini-1.5-pro-latest' # Renomeado para evitar conflito se ainda usar Google em outro lugar
# AI_GENERATION_TEMPERATURE_GOOGLE = 1.0
# AI_MAX_QUESTIONS_PER_REQUEST_GOOGLE = 50
# GOOGLE_AI_SAFETY_SETTINGS = [
#     {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_LOW_AND_ABOVE"},
#     {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_LOW_AND_ABOVE"},
#     {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
#     {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
# ]

# Validação para Ollama (Opcional, mas bom para debug inicial)
if DEBUG:
    if not OLLAMA_HOST:
        print("\n\nAVISO: OLLAMA_HOST não definido. Usando padrão 'http://localhost:11434'.\n")
    if not OLLAMA_MODEL_NAME:
        print("\n\nAVISO: OLLAMA_MODEL_NAME não definido. Usando padrão 'gemma:latest'.\n")
# Em produção, você pode querer levantar ImproperlyConfigured se não estiverem definidos e forem essenciais.


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'generator',
    'markdownify.apps.MarkdownifyConfig',
    'django.contrib.humanize',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # Para encontrar templates/registration/login.html
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
# Mantendo SQLite para simplicidade, conforme seu arquivo original.
# A seção comentada do PostgreSQL pode ser usada se você mudar de banco.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]


# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Boa_Vista' # Mantido conforme seu original
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')


# Configuração de armazenamento para Whitenoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- Configurações de Autenticação ---
LOGOUT_REDIRECT_URL = '/'
LOGIN_REDIRECT_URL = '/' # Redireciona para a URL raiz (landing page)


# --- Configuração de Logging ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}', 'style': '{',},
        'simple': {'format': '{levelname} {asctime} {module} {message}', 'style': '{',}, # Adicionado asctime e module para mais contexto
    },
    'handlers': {
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'), # Permite configurar via .env
            'propagate': False,
        },
        'generator': { # Logger da sua app 'generator'
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO', # Mais verboso em DEBUG para sua app
            'propagate': False,
        },
        'ollama': { # Logger específico para a biblioteca ollama, se ela usar logging
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'whitenoise': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}