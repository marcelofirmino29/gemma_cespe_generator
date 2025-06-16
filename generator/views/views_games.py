from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib import messages

# A única importação de 'views' necessária é a da função de contexto.
from .views_service_context import _get_base_context_and_service
from ..models import Topico, Questao, KahootGame, AreaConhecimento
from ..exceptions import AIServiceError

@login_required
def games_hub_view(request):
    """Renderiza a página que lista os jogos disponíveis."""
    context, _, _ = _get_base_context_and_service()
    return render(request, 'generator/jogos/games_hub.html', context)

@login_required
def kahoot_hub_view(request):
    """Página que oferece as opções de criar ou entrar em um jogo Kahoot."""
    return render(request, 'generator/jogos/kahoot_hub.html')

@login_required
def criar_kahoot_view(request):
    """
    Renderiza a página de criação de jogos Kahoot e lida com as 3 lógicas de criação.
    """
    # Padrão CORRETO: obtém o contexto, o objeto do serviço e o status de inicialização
    context, service, service_initialized = _get_base_context_and_service()

    if request.method == 'POST':
        num_questoes = int(request.POST.get('num_questoes', 10))
        questoes_ids = []
        jogo_topico_nome = "Jogo Personalizado"
        
        default_area = AreaConhecimento.objects.first()
        if not default_area:
            default_area, _ = AreaConhecimento.objects.get_or_create(nome="Geral")

        with transaction.atomic():
            if 'criar_por_topico' in request.POST:
                topico = get_object_or_404(Topico, pk=request.POST.get('topico'))
                jogo_topico_nome = topico.nome
                questoes = Questao.objects.filter(topico=topico, gerada_por_ia_para_jogo=False, tipo='CE').order_by('?')[:num_questoes]
                questoes_ids = list(questoes.values_list('id', flat=True))

            elif 'criar_por_area' in request.POST:
                area = get_object_or_404(AreaConhecimento, pk=request.POST.get('area'))
                jogo_topico_nome = f"Área: {area.nome}"
                questoes = Questao.objects.filter(topico__area_conhecimento=area, gerada_por_ia_para_jogo=False, tipo='CE').order_by('?')[:num_questoes]
                questoes_ids = list(questoes.values_list('id', flat=True))

            elif 'criar_por_ia' in request.POST:
                # CORRIGIDO: Verifica se o serviço foi inicializado corretamente
                if not service_initialized:
                    messages.error(request, "Serviço de IA não está disponível. Verifique as configurações.")
                    context['areas'] = AreaConhecimento.objects.all()
                    context['topicos'] = Topico.objects.all().select_related('area_conhecimento')
                    return render(request, 'generator/jogos/kahoot_criar.html', context)

                tema_ia = request.POST.get('tema_ia')
                jogo_topico_nome = f"IA: {tema_ia[:30]}..."
                
                # CORRIGIDO: Usa a variável 'service' que já é o objeto correto
                generated_data = service.generate_ce_questions_from_text(text_content=tema_ia, num_questions=num_questoes)
                
                novas_questoes = []
                for item in generated_data:
                    q = Questao.objects.create(
                        enunciado=item.get('enunciado', 'Enunciado não gerado.'),
                        gabarito_ce=item.get('gabarito', 'C'),
                        tipo='CE',
                        topico=Topico.objects.filter(area_conhecimento=default_area).first(),
                        criado_por=request.user,
                        gerada_por_ia_para_jogo=True
                    )
                    novas_questoes.append(q)
                questoes_ids = [q.id for q in novas_questoes]
            
            if not questoes_ids:
                context['error_message'] = "Não foi possível encontrar ou gerar questões para o tema selecionado."
                messages.error(request, context['error_message'])
            else:
                topico_jogo, _ = Topico.objects.get_or_create(nome=jogo_topico_nome, area_conhecimento=default_area)
                game = KahootGame.objects.create(host=request.user, topico_descritivo=topico_jogo)
                game.questoes.set(questoes_ids)
                return redirect('generator:kahoot_lobby', game_pin=game.pin)

    context['topicos'] = Topico.objects.all().select_related('area_conhecimento')
    context['areas'] = AreaConhecimento.objects.all()
    
    return render(request, 'generator/jogos/kahoot_criar.html', context)

@login_required
def entrar_kahoot_view(request):
    return render(request, 'generator/jogos/kahoot_entrar.html')

@login_required
def kahoot_lobby_view(request, game_pin):
    game = get_object_or_404(KahootGame, pin=game_pin)
    is_host = (request.user == game.host)
    context = {'game': game, 'is_host': is_host}
    return render(request, 'generator/jogos/kahoot_lobby.html', context)

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