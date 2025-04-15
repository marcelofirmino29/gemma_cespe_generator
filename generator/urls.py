# generator/urls.py
from django.urls import path
from . import views # Importa as views do app atual

# Opcional, mas boa prática: definir um namespace para o app
# app_name = 'generator'

urlpatterns = [
    # --- ADICIONE ESTA LINHA ---
    path('test_print/', views.test_print_view, name='test_print'),
    # --------------------------
    path('', views.generate_questions_view, name='generate_questions'),
    path('validate/', views.validate_answers_view, name='validate_answers'),
    # ... outras URLs se houver ...
]