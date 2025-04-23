# generator/urls.py
from django.urls import path
from . import views

# --- ESSENCIAL: Define o namespace para este aplicativo ---
app_name = 'generator'

urlpatterns = [
    # URLs da aplicação generator
    path('', views.landing_page_view, name='landing_page'),
    path('questions-ce/', views.generate_questions_view, name='generate_questions'),
    path('validate/', views.validate_answers_view, name='validate_answers'),
    path('generate-discursive/', views.generate_discursive_view, name='generate_discursive_answer'),
    path('generate-discursive-exam/', views.generate_discursive_exam_view, name='generate_discursive_exam'),
    path('evaluate-discursive/', views.evaluate_discursive_answer_view, name='evaluate_discursive_answer'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('validate-single-ce/', views.validate_single_ce_view, name='validate_single_ce'),

    # URLs do Módulo Simulado
    path('simulado/configurar/', views.configurar_simulado_view, name='configurar_simulado'),
    path('simulado/realizar/', views.realizar_simulado_view, name='realizar_simulado'),
    path('simulado/resultado/', views.resultado_simulado_view, name='resultado_simulado'),

    # URLs do Módulo Jogos
    # <<< URL FALTANTE ADICIONADA AQUI >>>
    path('jogos/', views.games_hub_view, name='games_hub'),
    path('jogo/arrastar-soltar/ml/', views.drag_drop_ml_game_view, name='drag_drop_ml_game'), # URL do jogo específico

    # URL de Teste
    path('test-print/', views.test_print_view, name='test_print'),

    # --- URL de Registro (geralmente no final) ---
    path('accounts/register/', views.register_view, name='register'),
]
