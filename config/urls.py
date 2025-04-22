from django.contrib import admin
from django.urls import path, include
from generator.views import register_view  # Aqui sim você importa views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Autenticação padrão do Django
    path('accounts/', include('django.contrib.auth.urls')),

    # Registro personalizado
    path('accounts/register/', register_view, name='register'),

    # Demais rotas do app
    path('', include('generator.urls')),
]
