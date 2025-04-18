# config/urls.py (AJUSTADO)

from django.contrib import admin
from django.urls import path, include # Certifique-se que 'include' está importado

urlpatterns = [
    path('admin/', admin.site.urls),

    # <<< ADICIONADO: URLs de Autenticação do Django >>>
    # Isso ativa as views/URLs para login, logout, mudança de senha, etc.
    # Elas estarão disponíveis em caminhos como /accounts/login/, /accounts/logout/, etc.
    path('accounts/', include('django.contrib.auth.urls')),
    # <<< FIM DA ADIÇÃO >>>

    # Inclui as URLs do seu app generator na raiz do site
    path('', include('generator.urls')),
]