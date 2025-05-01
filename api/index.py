import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')  # ajuste para o nome do seu projeto
app = get_wsgi_application()
