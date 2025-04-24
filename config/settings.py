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

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')


# --- Configurações da IA ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
AI_MODEL_NAME = 'gemini-1.5-pro-latest'
AI_GENERATION_TEMPERATURE = 1.0
AI_MAX_QUESTIONS_PER_REQUEST = 20

# Configurações de Segurança para a API Google AI (Usando Strings)
# Em settings.py

GOOGLE_AI_SAFETY_SETTINGS = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        # <<< ALTERADO PARA O MAIS FORTE >>>
        "threshold": "BLOCK_LOW_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        # <<< ALTERADO PARA O MAIS FORTE >>>
        "threshold": "BLOCK_LOW_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        # Mantenha como estava ou ajuste também se necessário
        "threshold": "BLOCK_MEDIUM_AND_ABOVE", # Ou BLOCK_LOW_AND_ABOVE
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
         # Mantenha como estava ou ajuste também se necessário
        "threshold": "BLOCK_MEDIUM_AND_ABOVE", # Ou BLOCK_LOW_AND_ABOVE
    },
]

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
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# Database
DATABASES = {
    'default': {
        'ENGINE': os.getenv('DATABASE_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.getenv('DATABASE_NAME', 'seu_projeto_db'),
        'USER': os.getenv('DATABASE_USER', 'seu_usuario_db'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD', 'sua_senha_db'),
        'HOST': os.getenv('DATABASE_HOST', 'seu_host_db'),
        'PORT': os.getenv('DATABASE_PORT', '5432'),
    }
}

# Password validation
# É recomendado adicionar os validadores padrão aqui:
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


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
# STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- Configurações de Autenticação ---

# Redirecionamento após Logout (Já estava ok)
LOGOUT_REDIRECT_URL = '/'

# <<< LINHA ADICIONADA ABAIXO >>>
# Redirecionamento após Login
LOGIN_REDIRECT_URL = '/' # Redireciona para a URL raiz (landing page)


# --- Configuração de Logging ---
LOGGING = {
    # ... (Configuração de Logging como antes) ...
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}', 'style': '{',},
        'simple': {'format': '{levelname} {message}', 'style': '{',},
    },
    'handlers': {
        'console': {'level': 'DEBUG', 'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False,},
        'generator': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False,},
    },
}