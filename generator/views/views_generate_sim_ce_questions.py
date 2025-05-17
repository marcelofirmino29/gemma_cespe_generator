from django.contrib import messages
from venv import logger
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.db.models import Q
from generator.forms import SimuladoConfigForm
from generator.models import Avaliacao, Questao, TentativaResposta
from django.utils import timezone
from venv import logger

from generator.models import Avaliacao, Questao, TentativaResposta
from generator.views.views_service_context import _get_base_context_and_service
# # --- Sua função _get_base_context_and_service ---

# --- VISÃO Configuração do Simulado (COM FILTRO DE TÓPICO) ---
@login_required
def configurar_simulado_view(request):
    context, _, _ = _get_base_context_and_service()
    form = SimuladoConfigForm(request.POST or None)
    context['form'] = form # Adiciona o form ao contexto para GET e POST inválido

    if request.method == 'POST':
        if form.is_valid():
            num_ce = form.cleaned_data.get('num_ce')
            area_obj = form.cleaned_data.get('area') # Objeto AreaConhecimento ou None
            dificuldade_ce = form.cleaned_data.get('dificuldade_ce') # String ou None
            topico_filtro = form.cleaned_data.get('topico', '').strip() # String ou vazia

            area_nome_log = area_obj.nome if area_obj else 'Todas'
            dif_log = dificuldade_ce or 'Qualquer'
            top_log = topico_filtro or 'Qualquer'
            logger.info(f"Configurando simulado C/E para {request.user.username}: "
                        f"Num={num_ce}, Area='{area_nome_log}', Dif='{dif_log}', Tópico='{top_log}'")

            selected_ids = []
            try:
                # Filtros base C/E
                ce_queryset = Questao.objects.filter(tipo='CE')

                # Aplica filtros opcionais
                if area_obj:
                    ce_queryset = ce_queryset.filter(area=area_obj)
                if dificuldade_ce:
                    ce_queryset = ce_queryset.filter(dificuldade=dificuldade_ce)
                if topico_filtro:
                    # Busca no nome do tópico (se relacionado) OU no texto do comando/motivador
                    ce_queryset = ce_queryset.filter(
                        Q(topico__nome__icontains=topico_filtro) | # Assumindo relação 'topico' com 'nome'
                        Q(texto_comando__icontains=topico_filtro) |
                        Q(texto_motivador__icontains=topico_filtro)
                    )
                    logger.info(f"Filtrando questões por tópico/texto contendo: '{topico_filtro}'")

                # Seleciona aleatoriamente até o número desejado
                selected_ids = list(ce_queryset.order_by('?').values_list('id', flat=True)[:num_ce])

                if not selected_ids:
                    messages.error(request, "Nenhuma questão C/E encontrada com os critérios selecionados. Ajuste os filtros e tente novamente.")
                    logger.warning(f"Nenhuma questão encontrada para simulado de {request.user.username} com filtros: Area={area_nome_log}, Dif={dif_log}, Tópico={top_log}")
                    # Re-renderiza o form com a mensagem de erro
                    return render(request, 'generator/configurar_simulado.html', context)

                if len(selected_ids) < num_ce:
                    messages.warning(request, f"Aviso: Apenas {len(selected_ids)} questões C/E encontradas com os critérios selecionados (você pediu {num_ce}).")
                    logger.info(f"Encontradas {len(selected_ids)}/{num_ce} questões para simulado de {request.user.username}.")


                # Armazena na sessão (salvando os IDs, não os objetos)
                request.session['simulado_config'] = {
                    'num_ce': len(selected_ids), # Salva o número real de questões selecionadas
                    'area_id': area_obj.id if area_obj else None,
                    'area_nome': area_obj.nome if area_obj else 'Todas', # Guarda nome para exibição
                    'dificuldade_ce': dificuldade_ce,
                    'topico_filtro': topico_filtro,
                }
                request.session['simulado_questao_ids'] = selected_ids
                request.session['simulado_indice_atual'] = 0 # Começa no índice 0
                # request.session['simulado_respostas'] = {} # Não parece ser usado, pode remover se não for necessário

                logger.info(f"Simulado C/E configurado para {request.user.username}. Questões IDs: {selected_ids}. Redirecionando...")
                messages.success(request, f"Simulado com {len(selected_ids)} questões C/E pronto para começar!")
                return redirect('generator:realizar_simulado')

            except Exception as e:
                logger.error(f"Erro ao selecionar questões C/E para o simulado: {e}", exc_info=True)
                messages.error(request, "Ocorreu um erro inesperado ao preparar o simulado. Tente novamente.")
                # Re-renderiza o form
                return render(request, 'generator/configurar_simulado.html', context)
        else: # Form inválido
            logger.warning(f"Formulário de configuração de simulado inválido: {form.errors.as_json()}")
            # O template exibirá os erros do form

    # Para GET ou POST inválido
    return render(request, 'generator/configurar_simulado.html', context)

@login_required
def realizar_simulado_view(request):
    context, _, _ = _get_base_context_and_service()
    questao_ids = request.session.get('simulado_questao_ids', [])
    # Índice da questão a ser exibida/processada AGORA (começa em 0)
    indice_atual = request.session.get('simulado_indice_atual', 0)

    # --- Lógica para POST (Recebe resposta da questão anterior) ---
    if request.method == 'POST':
        resposta_submetida = request.POST.get('resposta_simulado') # Espera 'C' ou 'E'
        questao_id_respondida = request.POST.get('questao_id') # ID da questão que foi exibida

        # Validações básicas
        if not questao_id_respondida or resposta_submetida is None:
            messages.warning(request, "Resposta ou ID da questão ausente. Tente novamente.")
            logger.warning(f"POST realizar_simulado sem ID ({questao_id_respondida}) ou resposta ({resposta_submetida}) por {request.user.username}")
            # Recarrega a mesma questão para o usuário tentar de novo
            return redirect('generator:realizar_simulado')

        if not questao_ids:
             messages.error(request, "Erro: Configuração do simulado não encontrada na sessão.")
             logger.error(f"POST realizar_simulado sem 'simulado_questao_ids' na sessão por {request.user.username}")
             return redirect('generator:configurar_simulado')

        try:
            # Verifica se o ID respondido é o esperado para o índice atual
            # Isso previne submissões fora de ordem ou após o término
            if indice_atual >= len(questao_ids) or int(questao_id_respondida) != questao_ids[indice_atual]:
                 messages.error(request, "Erro de sequência no simulado ou simulado já finalizado. Reiniciando configuração.")
                 logger.error(f"Erro de sequência/índice em realizar_simulado por {request.user.username}. Índice sessão: {indice_atual}, ID recebido: {questao_id_respondida}, IDs sessão: {questao_ids}")
                 # Limpa sessão do simulado
                 request.session.pop('simulado_questao_ids', None)
                 request.session.pop('simulado_indice_atual', None)
                 request.session.pop('simulado_config', None)
                 return redirect('generator:configurar_simulado')

            # Busca o objeto Questao
            questao_obj = Questao.objects.get(id=questao_id_respondida)

            # Valida a resposta C/E
            resposta_ce_valida = resposta_submetida.strip().upper()
            if questao_obj.tipo != 'CE' or resposta_ce_valida not in ['C', 'E']:
                 messages.error(request, f"Resposta inválida ('{resposta_submetida}') para questão C/E.")
                 logger.warning(f"Resposta inválida '{resposta_submetida}' para Q ID {questao_id_respondida} por {request.user.username}")
                 return redirect('generator:realizar_simulado') # Recarrega questão atual

            # Salva/Atualiza TentativaResposta
            tentativa, t_created = TentativaResposta.objects.update_or_create(
                usuario=request.user,
                questao=questao_obj,
                defaults={'resposta_ce': resposta_ce_valida, 'data_resposta': timezone.now()}
            )
            logger.info(f"Tentativa ID {tentativa.id} {'criada' if t_created else 'atualizada'} p/ Q ID {questao_id_respondida} no simulado por {request.user.username}.")

            # Salva/Atualiza Avaliação C/E
            is_correct = (tentativa.resposta_ce == questao_obj.gabarito_ce)
            score = 1 if is_correct else -1
            avaliacao, a_created = Avaliacao.objects.update_or_create(
                tentativa=tentativa,
                defaults={'correto_ce': is_correct, 'score_ce': score}
            )
            logger.info(f"Avaliacao C/E {'criada' if a_created else 'atualizada'} p/ Tentativa ID {tentativa.id}. Correto: {is_correct}")

            # <<< CORREÇÃO: Incrementa o índice ATUAL da sessão para a PRÓXIMA questão >>>
            indice_proxima = indice_atual + 1
            request.session['simulado_indice_atual'] = indice_proxima
            logger.info(f"Usuário {request.user.username} respondeu índice {indice_atual} (Q ID {questao_id_respondida}), avançando para índice {indice_proxima}.")

        except Questao.DoesNotExist:
            messages.error(request, "Erro: A questão respondida não foi encontrada.")
            logger.error(f"Questão ID {questao_id_respondida} não encontrada no DB durante simulado por {request.user.username}")
            request.session.pop('simulado_questao_ids', None); request.session.pop('simulado_indice_atual', None)
            return redirect('generator:configurar_simulado')
        except IndexError: # Caso o índice calculado seja inválido (raro com a verificação acima)
            messages.error(request, "Erro: Índice inválido no simulado.")
            logger.error(f"IndexError em realizar_simulado por {request.user.username}. Índice: {indice_atual}, Total IDs: {len(questao_ids)}")
            request.session.pop('simulado_questao_ids', None); request.session.pop('simulado_indice_atual', None)
            return redirect('generator:configurar_simulado')
        except Exception as e:
            logger.error(f"Erro inesperado ao salvar tentativa/avaliação do simulado: {e}", exc_info=True)
            messages.error(request, "Ocorreu um erro ao salvar sua resposta. Tente novamente.")
            # Não avança o índice, recarrega a mesma questão
            return redirect('generator:realizar_simulado')

        # Redireciona para si mesmo (GET) para carregar a próxima questão ou finalizar
        return redirect('generator:realizar_simulado')

    # --- Lógica para GET (Exibe a questão atual ou finaliza) ---
    if not questao_ids:
        messages.warning(request, "Simulado não iniciado ou configuração perdida. Por favor, configure novamente.")
        logger.warning(f"GET realizar_simulado sem 'simulado_questao_ids' na sessão por {request.user.username}")
        return redirect('generator:configurar_simulado')

    # Verifica se o índice atual já ultrapassou a lista de questões (fim do simulado)
    if indice_atual >= len(questao_ids):
        messages.success(request, "Simulado concluído!")
        # Guarda os IDs finalizados para a página de resultado e limpa a sessão do simulado atual
        simulado_finalizado_ids = request.session.pop('simulado_questao_ids', [])
        request.session['finalizado_simulado_questao_ids'] = simulado_finalizado_ids # Guarda para resultado
        request.session.pop('simulado_indice_atual', None)
        # request.session.pop('simulado_respostas', None) # Removido se não usado
        # request.session.pop('simulado_config', None) # Pode manter config para exibir no resultado

        logger.info(f"Simulado finalizado para {request.user.username}. IDs: {simulado_finalizado_ids}. Redirecionando para resultados.")
        return redirect('generator:resultado_simulado') # Redireciona para a página de resultado

    # Se ainda há questões, busca a questão do índice atual para exibir
    questao_id_atual = questao_ids[indice_atual]
    try:
        questao_atual = Questao.objects.select_related('area').get(id=questao_id_atual)
        context['questao'] = questao_atual
        context['indice_atual'] = indice_atual + 1 # Para exibição (Questão 1 de N, 2 de N, ...)
        context['total_questoes'] = len(questao_ids)
        # Passa a configuração para o template, se existir
        context['simulado_config'] = request.session.get('simulado_config', {})

        logger.info(f"Exibindo questão índice {indice_atual} (ID: {questao_id_atual}) para {request.user.username}. Total: {len(questao_ids)}")
    except Questao.DoesNotExist:
        messages.error(request, f"Erro: A questão {indice_atual + 1} do simulado (ID: {questao_id_atual}) não foi encontrada.")
        logger.error(f"Questão ID {questao_id_atual} (índice {indice_atual}) não encontrada no DB durante GET realizar_simulado por {request.user.username}")
        request.session.pop('simulado_questao_ids', None); request.session.pop('simulado_indice_atual', None)
        return redirect('generator:configurar_simulado')
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar questão {questao_id_atual} para o simulado: {e}", exc_info=True)
        messages.error(request, "Ocorreu um erro ao carregar a próxima questão do simulado.")
        return redirect('generator:configurar_simulado') # Volta para configuração

    return render(request, 'generator/realizar_simulado.html', context)

# --- VIEW: Resultado do Simulado ---
@login_required
def resultado_simulado_view(request):
    """Exibe os resultados e estatísticas do último simulado concluído."""
    context, _, _ = _get_base_context_and_service()
    # Pega os IDs das questões do simulado finalizado da sessão
    # Usa .get() para não dar erro se a chave não existir, retorna lista vazia
    questao_ids = request.session.get('finalizado_simulado_questao_ids', [])
    simulado_config = request.session.get('simulado_config', {}) # Pega config também

    # Limpa as chaves da sessão após pegá-las (ou se não existirem)
    request.session.pop('finalizado_simulado_questao_ids', None)
    # request.session.pop('simulado_config', None) # Decide se quer limpar a config

    if not questao_ids:
        messages.warning(request, "Não há resultados de simulado para exibir ou a sessão expirou.")
        logger.warning(f"Acesso a resultado_simulado_view sem 'finalizado_simulado_questao_ids' por {request.user.username}")
        return redirect('generator:dashboard') # Ou para 'configurar_simulado'

    logger.info(f"Exibindo resultado do simulado para {request.user.username}. Questões IDs: {questao_ids}")

    tentativas_do_simulado = []
    stats_simulado = {}

    try:
        # Busca as tentativas e avaliações APENAS para as questões deste simulado
        # Garante que busca apenas as do usuário logado
        tentativas_do_simulado = TentativaResposta.objects.filter(
            usuario=request.user,
            questao_id__in=questao_ids # Filtra pelos IDs do simulado
        ).select_related(
            'questao', 'questao__area'
        ).prefetch_related(
            'avaliacao'
        ).order_by('data_resposta') # Ordena pela ordem de resposta (ou pode usar a ordem de questao_ids se preferir)

        # Calcula Estatísticas Específicas do Simulado
        total_respondidas = tentativas_do_simulado.count()
        total_ce = 0; acertos_ce = 0; erros_ce = 0
        # Adicione contadores para discursivas se simulados puderem incluí-las no futuro
        # total_disc = 0; ...

        for t in tentativas_do_simulado:
            if t.questao.tipo == 'CE':
                total_ce += 1
                avaliacao = getattr(t, 'avaliacao', None) # Pega do prefetch
                if avaliacao and avaliacao.correto_ce is not None:
                    if avaliacao.correto_ce: acertos_ce += 1
                    else: erros_ce += 1
            # elif t.questao.tipo == 'DISC':
                # Lógica para discursiva se aplicável no futuro

        # Stats C/E
        score_ce = acertos_ce - erros_ce
        # Calcula percentual baseado no total de C/E respondidas no simulado
        percentual_ce = round((acertos_ce / total_ce) * 100) if total_ce > 0 else 0

        stats_simulado = {
            'total_questoes_planejado': simulado_config.get('num_ce', len(questao_ids)), # Total planejado
            'total_respondidas': total_respondidas, # Total efetivamente respondido/salvo
            'total_ce': total_ce, # Total de C/E respondidas
            'acertos_ce': acertos_ce,
            'erros_ce': erros_ce,
            'score_ce': score_ce,
            'percentual_ce': percentual_ce,
            # Adicionar outras stats (discursivas) se necessário
            'config': simulado_config # Passa a configuração usada no simulado
        }
        logger.info(f"Stats do Simulado para {request.user.username}: {stats_simulado}")

        if total_respondidas < len(questao_ids):
             messages.warning(request, f"Atenção: Você respondeu {total_respondidas} de {len(questao_ids)} questões planejadas para este simulado.")

    except Exception as e:
        logger.error(f"Erro ao buscar/calcular resultado do simulado para {request.user.username} (IDs: {questao_ids}): {e}", exc_info=True)
        messages.error(request, "Ocorreu um erro ao carregar os resultados detalhados do simulado.")
        # Não limpa a lista de tentativas para debug se necessário
        stats_simulado = {'config': simulado_config} # Passa pelo menos a config

    context['tentativas_simulado'] = tentativas_do_simulado # Passa a lista de tentativas deste simulado
    context['stats_simulado'] = stats_simulado # Passa as estatísticas deste simulado

    return render(request, 'generator/resultado_simulado.html', context)
# --- FIM VIEW RESULTADO ---
