# config/urls.py
from django.contrib import admin
from django.urls import path, include # Certifique-se que 'include' está importado

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('generator.urls')), # Inclui as URLs do app generator na raiz
]