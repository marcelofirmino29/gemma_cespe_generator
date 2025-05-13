# --- VIEW PARA O HUB DE JOGOS ---
from django.shortcuts import render
from generator.views.views_service_context import _get_base_context_and_service
from django.contrib.auth.decorators import login_required

@login_required
def games_hub_view(request):
    """Renderiza a página que lista os jogos disponíveis."""
    context, _, _ = _get_base_context_and_service()
    available_games = [
        {
            'name': 'Arrastar e Soltar: Algoritmos ML',
            'description': 'Associe algoritmos como SVM, KNN e K-Means às suas categorias.',
            'url_name': 'generator:drag_drop_ml_game', # Nome da URL definida em urls.py
            'icon': 'bi-arrows-move' # Classe do ícone Bootstrap Icons
        },
        {
             'name': 'Caça-Palavras: Termos LGPD',
             'description': 'Encontre termos importantes da Lei Geral de Proteção de Dados.',
             'url_name': 'generator:word_search_lgpd_game',
             'icon': 'bi-search'
        },
         {
             'name': 'Aprendendo JS com Blocos',
             'description': 'Uma introdução interativa à lógica de programação JavaScript.',
             'url_name': 'generator:scratch_js_game',
             'icon': 'bi-puzzle-fill'
         },
        # Adicione mais jogos aqui conforme são criados
    ]
    context['games'] = available_games
    # Aponta para o template do hub de jogos
    return render(request, 'generator/jogos/games_hub.html', context)


# --- VIEW PARA O JOGO DE ARRASTAR E SOLTAR ML ---
@login_required
def drag_drop_ml_game_view(request):
    """Renderiza a página do jogo de arrastar e soltar sobre algoritmos de ML."""
    context, _, _ = _get_base_context_and_service()
    # Aponta para o template específico do jogo
    return render(request, 'generator/jogos/game_drag_drop_ml.html', context)

# --- VIEW PARA O JOGO ESTILO SCRATCH JS ---
@login_required
def scratch_js_view(request):
    """Renderiza a página estilo Scratch para aprender JS."""
    context, _, _ = _get_base_context_and_service()
    # A lógica principal será no frontend (HTML/JS)
    return render(request, 'generator/jogos/scratch_js_learning.html', context)

# --- VIEW PARA O JOGO CAÇA-PALAVRAS LGPD ---
@login_required
def word_search_lgpd_view(request):
    """Renderiza a página do jogo de caça-palavras sobre LGPD."""
    context, _, _ = _get_base_context_and_service()
    return render(request, 'generator/jogos/game_word_search_lgpd.html', context)


@login_required # Mantém o requisito de login, remova se o jogo for público
def aventura_dados_view(request):
    """
    Renderiza a página do jogo Aventura de Dados.
    """
    # Se precisar de contexto base (usuário, etc.), use a função auxiliar
    # context, _, _ = _get_base_context_and_service()
    # Se não precisar de contexto extra, pode usar um dicionário vazio:
    context = {}
    return render(request, 'generator/jogos/aventura_dados.html', context)