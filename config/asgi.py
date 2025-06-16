# config/asgi.py

import os
from django.core.asgi import get_asgi_application

# PASSO 1: Configurar o ambiente do Django PRIMEIRO.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# PASSO 2: Chamar get_asgi_application() para garantir que o Django
# se inicialize e que os apps (incluindo os modelos) estejam prontos.
django_asgi_app = get_asgi_application()

# PASSO 3: AGORA que o Django está pronto, podemos importar
# com segurança os componentes do Channels e do nosso projeto.
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
import generator.routing

# PASSO 4: Montar a aplicação final.
application = ProtocolTypeRouter({
    "http": django_asgi_app,  # Usa a aplicação Django já inicializada para HTTP.
    "websocket": AuthMiddlewareStack(
        URLRouter(
            generator.routing.websocket_urlpatterns
        )
    ),
})