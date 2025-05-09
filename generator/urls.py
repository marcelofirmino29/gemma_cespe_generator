# generator/urls.py
from django.urls import path
from . import views

# --- ESSENCIAL: Define o namespace para este aplicativo ---
app_name = 'generator'

urlpatterns = [
    # URLs da aplicação generator
    path('', views.landing_page_view, name='landing_page'),

    path('questions_ce/', views.listar_questoes_ce_view, name='questions_ce'),
    path('gerar-questoes-ce/', views.generate_questions_view, name='generate_questions'),

    path('validate/', views.validate_answers_view, name='validate_answers'),

    path('upload-pdf-generate/', views.upload_pdf_and_generate_questions_view, name='upload_pdf_generate'),

    path('generate-discursive-exam/', views.generate_discursive_exam_view, name='generate_discursive_exam'),
    path('evaluate-discursive/', views.evaluate_discursive_answer_view, name='evaluate_discursive_answer'),
    path('questions_discursivas/', views.listar_questoes_discursivas_view, name='questions_discursivas'), # View deve existir em views.py
    path('concursos/', views.listar_concursos_view, name='listar_concursos'), # <<< NOVA URL

    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('validate-single-ce/', views.validate_single_ce_view, name='validate_single_ce'),

    # URLs do Módulo Simulado
    path('simulado/configurar/', views.configurar_simulado_view, name='configurar_simulado'),
    path('simulado/realizar/', views.realizar_simulado_view, name='realizar_simulado'),
    path('simulado/resultado/', views.resultado_simulado_view, name='resultado_simulado'),

    # URLs do Módulo Jogos
    path('jogos/', views.games_hub_view, name='games_hub'),
    path('jogos/drag-drop-ml/', views.drag_drop_ml_game_view, name='game_drag_drop_ml'),
    path('jogos/word_search_lgpd_game', views.word_search_lgpd_view, name='word_search_lgpd_game'),
    path('jogos/aventura-dados/', views.aventura_dados_view, name='aventura_dados'),
    path('jogos/scratch-js/', views.scratch_js_view, name='scratch_js_game'),

    # Módulo de Perguntas
    path('pergunte-ia/', views.ask_ai_view, name='ask_ai'),

    # URL de Teste
    path('test-print/', views.test_print_view, name='test_print'),

    # --- URL de Registro ---
    path('accounts/register/', views.register_view, name='register'),

    # --- URLs de Área ---
    path('areas/', views.area_list_view, name='area_list'),
    path('areas/nova/', views.add_area_view, name='add_area'),
    path('add-area-quick-generator/', views.add_area_quick_from_generator_view, name='add_area_quick_from_generator')
]