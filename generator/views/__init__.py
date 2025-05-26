from .views_tests import * 
from .views_auth import register_view
from .views_validators import (landing_page_view,
                            validate_answers_view,
                            validate_single_ce_view,
                            ask_ai_view
)

from .views_functions import (extrair_texto_completo_pdf,
                              dashboard_view,
                              upload_pdf_and_generate_questions_view,
                              pdf_summary_view                          
)

from .views_generate_questions import (
    generate_questions_view,
    generate_discursive_exam_view,
    evaluate_discursive_answer_view,
    configurar_simulado_view,
    realizar_simulado_view,
    resultado_simulado_view,
    area_list_view,
    add_area_quick_from_generator_view,
    listar_questoes_ce_view,
    listar_questoes_discursivas_view
)

from .views_service_context import _get_base_context_and_service

from .views_games import (
    games_hub_view,
    drag_drop_ml_game_view,
    word_search_lgpd_view,
    aventura_dados_view,
    scratch_js_view,
)   

from .views_scraped_exams import listar_provas_coletadas

from .views_ext_api import listar_concursos_view

from .views_leis import listar_leis_coletadas_planalto, extract_and_markdownify_view

__all__ = {
    'register_view',
    'landing_page_view',
    'extrair_texto_completo_pdf', # Adicionado se esta é uma função pública pretendida
    'pdf_summary_view', # Adicionado se esta é uma função pública pretendida
    'generate_questions_view',    # Adicionado se esta é uma view pública pretendida
    'validate_answers_view',      # Adicionado se esta é uma view pública pretendida
    'validate_single_ce_view',    # Adicionado se esta é uma view pública pretendida
    'generate_discursive_exam_view', # Adicionado se esta é uma view pública pretendida
    'evaluate_discursive_answer_view', # Adicionado se esta é uma view pública pretendida
    'configurar_simulado_view',   # Adicionado se esta é uma view pública pretendida
    'realizar_simulado_view',     # Adicionado se esta é uma view pública pretendida
    'resultado_simulado_view'    # Adicionado se esta é uma view pública pretendida
    'dashboard_view', # Adicionado se esta é uma view pública pretendida
    'games_hub_view', # Adicionado se esta é uma view pública pretendida
    'drag_drop_ml_game_view', # Adicionado se esta é uma view pública pretendida
    'word_search_lgpd_view', # Adicionado se esta é uma view pública pretendida
    'aventura_dados_view', # Adicionado se esta é uma view pública pretendida
    'scratch_js_view', # Adicionado se esta é uma view pública pretendida
    'ask_ai_view', # Adicionado se esta é uma view pública pretendida
    'area_list_view', # Adicionado se esta é uma view pública pretendida
    'add_area_quick_from_generator_view', # Adicionado se esta é uma view pública pretendida
    'listar_questoes_ce_view' # Adicionado se esta é uma view pública pretendida
    'listar_questoes_discursivas_view' # Adicionado se esta é uma view pública pretendida
    'upload_pdf_and_generate_questions_view', # Adicionado se esta é uma view pública pretendida
    'listar_concursos_view', # Adicionado se esta é uma view pública pretendida
    'listar_provas_coletadas', # Adicionado se esta é uma view pública pretendida
    'listar_leis_coletadas_planalto', # Adicionado se esta é uma view pública pretendida
}
