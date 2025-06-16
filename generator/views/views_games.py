from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib import messages

# A única importação de 'views' necessária é a da função de contexto.
from .views_service_context import _get_base_context_and_service
from ..models import Topico, Questao, KahootGame, AreaConhecimento
from ..exceptions import AIServiceError

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from ..models import Topico, Questao, KahootGame, KahootPlayer

@login_required
def games_hub_view(request):
    """Renderiza a página que lista os jogos disponíveis."""
    context, _, _ = _get_base_context_and_service()
    return render(request, 'generator/jogos/games_hub.html', context)

@login_required
def criar_kahoot_view(request):
    if request.method == 'POST':
        topico_id = request.POST.get('topico')
        # Garante um valor padrão se num_questoes não for enviado ou for vazio
        try:
            num_questoes = int(request.POST.get('num_questoes', 5))
        except (ValueError, TypeError):
            num_questoes = 5

        topico = get_object_or_404(Topico, id=topico_id)
        
        # Filtra apenas por questões de Múltipla Escolha ('ME') para o Kahoot
        questoes = Questao.objects.filter(topico=topico, tipo='ME').order_by('?')[:num_questoes]
        
        # Opcional: Adicionar mensagem de erro se não houver questões suficientes
        if len(questoes) < 1:
            topicos = Topico.objects.all()
            return render(request, 'generator/jogos/kahoot_criar.html', {
                'topicos': topicos,
                'error': 'Não há questões de múltipla escolha suficientes para este tópico.'
            })

        # Cria o jogo com o host e o tópico
        game = KahootGame.objects.create(host=request.user, topico_descritivo=topico)
        game.questoes.set(questoes)
        
        # Redireciona para a nova tela de Host
        return redirect('generator:kahoot_host', game_pin=game.pin)

    topicos = Topico.objects.all()
    return render(request, 'generator/jogos/kahoot_criar.html', {'topicos': topicos})

def entrar_kahoot_view(request):
    if request.method == 'POST':
        pin = request.POST.get('pin', '').strip()
        nickname = request.POST.get('nickname', '').strip()
        
        if not pin or not nickname:
             return render(request, 'generator/jogos/kahoot_entrar.html', {'error': 'PIN e Apelido são obrigatórios.'})

        # Verifica se o jogo existe e está aguardando jogadores
        if not KahootGame.objects.filter(pin=pin, status='waiting').exists():
            return render(request, 'generator/jogos/kahoot_entrar.html', {'error': 'PIN inválido ou o jogo já começou.'})
        
        # Redireciona para a nova tela do Jogador
        return redirect('generator:kahoot_player', game_pin=pin, nickname=nickname)
        
    return render(request, 'generator/jogos/kahoot_entrar.html')

# NOVA View para a tela do Host (quem projeta o jogo)
@login_required
def kahoot_host_view(request, game_pin):
    game = get_object_or_404(KahootGame, pin=game_pin)
    # Garante que apenas o criador do jogo possa acessar a tela de host
    if game.host != request.user:
        return HttpResponseForbidden("Acesso negado. Você não é o host deste jogo.")
    
    # Renderiza o template da tela do host. Toda a lógica do jogo será via WebSocket.
    return render(request, 'generator/jogos/kahoot_host.html', {'game': game})

# NOVA View para a tela do Jogador (onde ele responde)
def kahoot_player_view(request, game_pin, nickname):
    # Apenas renderiza a página. A lógica de entrada e jogo é via WebSocket.
    return render(request, 'generator/jogos/kahoot_player.html', {
        'game_pin': game_pin, 
        'nickname': nickname
    })

# Views dos outros jogos
@login_required
def drag_drop_ml_game_view(request):
    context, _, _ = _get_base_context_and_service()
    return render(request, 'generator/jogos/game_drag_drop_ml.html', context)

@login_required
def scratch_js_view(request):
    context, _, _ = _get_base_context_and_service()
    return render(request, 'generator/jogos/scratch_js_learning.html', context)

@login_required
def word_search_lgpd_view(request):
    context, _, _ = _get_base_context_and_service()
    return render(request, 'generator/jogos/game_word_search_lgpd.html', context)

@login_required
def aventura_dados_view(request):
    context = {}
    return render(request, 'generator/jogos/aventura_dados.html', context)