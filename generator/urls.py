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
    path('jogos/', views.games_hub_view, name='games_hub'),
    path('jogo/arrastar-soltar/ml/', views.drag_drop_ml_game_view, name='drag_drop_ml_game'),
    path('jogo/scratch-js/', views.scratch_js_view, name='scratch_js_game'),
    path('jogo/word_search_lgpd_game', views.word_search_lgpd_view, name='word_search_lgpd_game'),

    # Módulo de Perguntas
    path('pergunte-ia/', views.ask_ai_view, name='ask_ai'),

    # URL de Teste
    path('test-print/', views.test_print_view, name='test_print'),

    # --- URL de Registro (geralmente no final) ---
    path('accounts/register/', views.register_view, name='register'),

# --- URLs de Área ---
    path('areas/', views.area_list_view, name='area_list'),
    path('areas/nova/', views.add_area_view, name='add_area'),
]