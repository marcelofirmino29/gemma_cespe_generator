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

DEBUG = False

#ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

ALLOWED_HOSTS = ['192.168.55.94','http://35.209.77.3/','https://generator-v1-2-754311810435.us-central1.run.app','.vercel.app','*'] # Mantenha como estava ou ajuste conforme necessário para produção
CSRF_TRUSTED_ORIGINS = ['https://generator-v1-2-754311810435.us-central1.run.app'] 


# --- Configurações da IA ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
AI_MODEL_NAME = 'gemini-1.5-pro-latest'
AI_GENERATION_TEMPERATURE = 1.0
AI_MAX_QUESTIONS_PER_REQUEST = 50

# Configurações de Segurança para a API Google AI (Usando Strings)
GOOGLE_AI_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_LOW_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_LOW_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

# Verifica se a chave da API foi carregada (ESSENCIAL)
if not GOOGLE_API_KEY:
    if not DEBUG:
         raise ImproperlyConfigured("FATAL: GOOGLE_API_KEY não definida nas variáveis de ambiente (.env).")
    else:
         print("\n\nAVISO: GOOGLE_API_KEY não definida. A geração de questões falhará.\nCrie um arquivo .env na raiz do projeto com GOOGLE_API_KEY=SUA_CHAVE\n")


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
    'django_celery_beat',

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


# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'TIMEOUT': 20000,  # Timeout in milliseconds (e.g., 20 seconds)
    }
}

# DATABASES = {
#     'default': {
#         'ENGINE': os.getenv('DATABASE_ENGINE', 'django.db.backends.postgresql'),
#         'HOST': os.getenv('DATABASE_HOST'), # Será lido do ambiente
#         'NAME': os.getenv('DATABASE_NAME'),       # Será lido do ambiente
#         'USER': os.getenv('DATABASE_USER'),       # Será lido do ambiente
#         'PASSWORD': os.getenv('DATABASE_PASSWORD'), # Será lido do ambiente
#         'HOST': os.getenv('DATABASE_HOST'),       # Será lido do ambiente (IP ou socket)
#         'PORT': os.getenv('DATABASE_PORT', '5432'), # Será lido do ambiente ou usa 5432
#     }
# }


# # Validação em produção
# if not DEBUG:
#     if not DATABASES['default'].get('NAME'): raise ImproperlyConfigured("DATABASE_NAME não definida.")
#     if not DATABASES['default'].get('USER'): raise ImproperlyConfigured("DATABASE_USER não definido.")
#     if not DATABASES['default'].get('PASSWORD'): raise ImproperlyConfigured("DATABASE_PASSWORD não definida.")
#     if not DATABASES['default'].get('HOST'): raise ImproperlyConfigured("DATABASE_HOST não definido.")

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]


# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Boa_Vista'
USE_I18N = True
USE_TZ = True

1
# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
#STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')


# <<< ADICIONADO: Configuração de armazenamento para Whitenoise >>>
# Usa armazenamento otimizado que adiciona compressão e cache eterno
# Apenas ativo quando DEBUG = False
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
# <<< FIM ADIÇÃO WHITENOISE >>>

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
        'simple': {'format': '{levelname} {message}', 'style': '{',},
    },
    'handlers': {
        'console': {'level': 'DEBUG' if DEBUG else 'INFO', 'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False,},
        'generator': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False,},
         # Adiciona logger para Whitenoise para ver mensagens (opcional)
        'whitenoise': {'handlers': ['console'], 'level': 'INFO', 'propagate': False,},
    },
}

# config/settings.py
# ...
SCRAPER_CONFIG_PCICONCURSOS = {
    'MAX_CATEGORIAS_CARGO': 5,
    'MAX_PAGINAS_POR_CATEGORIA': 2,
    'ANO_ALVO': None, # Ou um ano específico como string "2023"
    'MAX_PROFUNDIDADE_RECURSAO': 4,
    'USER_AGENT': 'Mozilla/5.0 (compatible; GemmaCespeGeneratorBot/1.0', # Seja transparente
}

# --- CELERY SETTINGS ---
CELERY_BROKER_HOST = os.getenv('CELERY_BROKER_HOST', 'localhost')
CELERY_BROKER_PORT = os.getenv('CELERY_BROKER_PORT', '6379')
CELERY_RESULT_BACKEND_HOST = os.getenv('CELERY_RESULT_BACKEND_HOST', CELERY_BROKER_HOST)
CELERY_RESULT_BACKEND_PORT = os.getenv('CELERY_RESULT_BACKEND_PORT', CELERY_BROKER_PORT)

CELERY_BROKER_URL = f'redis://{CELERY_BROKER_HOST}:{CELERY_BROKER_PORT}/0'
CELERY_RESULT_BACKEND = f'redis://{CELERY_RESULT_BACKEND_HOST}:{CELERY_RESULT_BACKEND_PORT}/1'

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
# --- FIM DAS CELERY SETTINGS ---