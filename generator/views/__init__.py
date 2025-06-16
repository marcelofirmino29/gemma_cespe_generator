# generator/views/__init__.py

from .views_tests import test_print_view
from .views_auth import register_view

from .views_validators import (
    landing_page_view,
    validate_answers_view,
    validate_single_ce_view,
    ask_ai_view
)

from .views_functions import (
    dashboard_view,
    upload_pdf_and_generate_questions_view,
    pdf_summary_view,
    extrair_texto_completo_pdf,
)

from .views_generate_questions import (
    generate_questions_view,
    generate_discursive_exam_view,
    evaluate_discursive_answer_view,
    configurar_simulado_view,
    realizar_simulado_view,
    resultado_simulado_view,
    add_area_quick_from_generator_view,
    listar_questoes_ce_view,
    listar_questoes_discursivas_view
)

# ALTERADO: Removida a antiga 'criar_kahoot_view'
from .views_games import (
    games_hub_view,
    drag_drop_ml_game_view,
    word_search_lgpd_view,
    aventura_dados_view,
    scratch_js_view,
    entrar_kahoot_view,
    kahoot_host_view,
    kahoot_player_view,
)   

# ADICIONADO: Import das novas views do editor de quiz
from .views_quiz_editor import (
    quiz_list_view,
    quiz_create_view,
    quiz_edit_view,
    quiz_delete_view,
    quiz_launch_view,
)

from .views_scraped_exams import listar_provas_coletadas
from .views_ext_api import listar_concursos_view
from .views_leis import listar_leis_coletadas_planalto, extract_and_markdownify_view

# __all__ corrigido para incluir as novas views e remover as antigas
__all__ = [
    'test_print_view',
    'register_view',
    'landing_page_view',
    'validate_answers_view',
    'validate_single_ce_view',
    'ask_ai_view',
    'dashboard_view',
    'upload_pdf_and_generate_questions_view',
    'pdf_summary_view',
    'extrair_texto_completo_pdf',
    'generate_questions_view',
    'generate_discursive_exam_view',
    'evaluate_discursive_answer_view',
    'configurar_simulado_view',
    'realizar_simulado_view',
    'resultado_simulado_view',
    'add_area_quick_from_generator_view',
    'listar_questoes_ce_view',
    'listar_questoes_discursivas_view',
    'games_hub_view',
    'drag_drop_ml_game_view',
    'word_search_lgpd_view',
    'aventura_dados_view',
    'scratch_js_view',
    'entrar_kahoot_view',
    'kahoot_host_view',
    'kahoot_player_view',
    'listar_provas_coletadas',
    'listar_concursos_view',
    'listar_leis_coletadas_planalto',
    'extract_and_markdownify_view',
    # Views do novo editor adicionadas
    'quiz_list_view',
    'quiz_create_view',
    'quiz_edit_view',
    'quiz_delete_view',
    'quiz_launch_view',
]