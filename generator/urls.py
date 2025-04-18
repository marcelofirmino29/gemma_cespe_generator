# generator/urls.py
from django.urls import path
from . import views

# app_name = 'generator'

urlpatterns = [
    path('', views.landing_page_view, name='landing_page'),
    path('questions-ce/', views.generate_questions_view, name='generate_questions'),
    path('validate/', views.validate_answers_view, name='validate_answers'),
    path('generate-discursive/', views.generate_discursive_view, name='generate_discursive_answer'),
    path('generate-discursive-exam/', views.generate_discursive_exam_view, name='generate_discursive_exam'),
    path('evaluate-discursive/', views.evaluate_discursive_answer_view, name='evaluate_discursive_answer'),
    path('accounts/register/', views.register_view, name='register'),

    # --- <<< NOVA URL PARA O DASHBOARD >>> ---
    path('dashboard/', views.dashboard_view, name='dashboard'),
    # --- <<< FIM NOVA URL >>> ---

    path('test-print/', views.test_print_view, name='test_print'),
]