# generator/urls.py
from django.urls import path
from . import views

# app_name = 'generator' # Descomente se for usar namespaces

urlpatterns = [
    # URLs existentes
    path('', views.landing_page_view, name='landing_page'),
    path('questions-ce/', views.generate_questions_view, name='generate_questions'),
    path('validate/', views.validate_answers_view, name='validate_answers'),
    path('generate-discursive/', views.generate_discursive_view, name='generate_discursive_answer'), # Gera a RESPOSTA modelo
    path('generate-discursive-exam/', views.generate_discursive_exam_view, name='generate_discursive_exam'), # Gera a QUESTÃO

    # --- NOVA URL para AVALIAR a resposta discursiva do usuário ---
    path('evaluate-discursive/', views.evaluate_discursive_answer_view, name='evaluate_discursive_answer'),
    # --- FIM NOVA URL ---

    path('test-print/', views.test_print_view, name='test_print'),
]