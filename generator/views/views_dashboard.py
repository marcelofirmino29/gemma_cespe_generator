from venv import logger
from django.contrib.auth.decorators import login_required
from datetime import datetime,timedelta
from django.contrib import messages
from django.shortcuts import render
from generator.models import AreaConhecimento, TentativaResposta
from generator.views.views_service_context import _get_base_context_and_service

@login_required
def dashboard_view(request):
    context, _, _ = _get_base_context_and_service()
    tentativas_recentes = []
    stats = {}
    date_from_obj = None # Data inicial do filtro
    date_to_obj = None # Data final do filtro

    # --- Lógica para Ler Filtros GET ---
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    area_filter_id = request.GET.get('area_filter') # Novo filtro de área

    # Converte datas string para objetos date
    if date_from_str:
        try: date_from_obj = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError: messages.warning(request, "Formato de data inicial inválido. Use AAAA-MM-DD."); date_from_obj = None
    if date_to_str:
        try: date_to_obj = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError: messages.warning(request, "Formato de data final inválido. Use AAAA-MM-DD."); date_to_obj = None

    area_filter_obj = None
    if area_filter_id:
        try: area_filter_obj = AreaConhecimento.objects.get(id=area_filter_id)
        except (AreaConhecimento.DoesNotExist, ValueError): messages.warning(request, "Área selecionada inválida."); area_filter_obj = None

    logger.info(f"Dashboard acessado por {request.user.username}. Filtros: Data=({date_from_str} a {date_to_str}), AreaID={area_filter_id}")

    try:
        # Busca base de TODAS as tentativas do usuário
        todas_tentativas_qs = TentativaResposta.objects.filter(
            usuario=request.user
        ).select_related( # Otimiza busca de dados relacionados
            'questao', 'questao__area'
        ).prefetch_related( # Otimiza busca reversa OneToOne
            'avaliacao'
        )

        # --- Aplica Filtros ---
        if date_from_obj:
            todas_tentativas_qs = todas_tentativas_qs.filter(data_resposta__date__gte=date_from_obj)
        if date_to_obj:
            # Adiciona 1 dia ao date_to para incluir o dia inteiro
            date_to_inclusive = date_to_obj + timedelta(days=1)
            todas_tentativas_qs = todas_tentativas_qs.filter(data_resposta__lt=date_to_inclusive) # Usa __lt com dia seguinte
        if area_filter_obj:
             todas_tentativas_qs = todas_tentativas_qs.filter(questao__area=area_filter_obj)

        # --- Cálculos (sobre o queryset filtrado) ---
        total_geral_filtrado = todas_tentativas_qs.count() # Total no período/área

        # Filtra C/E DENTRO do queryset já filtrado para estatísticas
        tentativas_ce_filtradas = todas_tentativas_qs.filter(questao__tipo='CE')
        total_ce_filtrado = tentativas_ce_filtradas.count()
        acertos_ce = 0; erros_ce = 0
        for t_ce in tentativas_ce_filtradas: # Itera SOMENTE nas C/E filtradas
            avaliacao = getattr(t_ce, 'avaliacao', None) # Pega do prefetch
            if avaliacao and avaliacao.correto_ce is not None: # Verifica se tem avaliação e se C/E foi avaliado
                if avaliacao.correto_ce: acertos_ce += 1
                else: erros_ce += 1
        score_ce = acertos_ce - erros_ce
        percentual_ce = round((acertos_ce / total_ce_filtrado) * 100) if total_ce_filtrado > 0 else 0

        # Filtra Discursivas DENTRO do queryset já filtrado
        tentativas_disc_filtradas = todas_tentativas_qs.filter(questao__tipo='DISC')
        total_disc_filtrado = tentativas_disc_filtradas.count()
        nc_total = 0.0; ne_total = 0; npd_total = 0.0; count_disc_avaliadas = 0
        for t_disc in tentativas_disc_filtradas:
             avaliacao = getattr(t_disc, 'avaliacao', None)
             # Soma apenas se a avaliação discursiva foi feita e tem notas válidas
             if avaliacao and avaliacao.nc is not None and avaliacao.ne is not None and avaliacao.npd is not None:
                  nc_total += avaliacao.nc
                  ne_total += avaliacao.ne
                  npd_total += avaliacao.npd
                  count_disc_avaliadas += 1
        # Médias Discursivas (calculadas apenas sobre as avaliadas no período/área)
        media_nc = round(nc_total / count_disc_avaliadas, 2) if count_disc_avaliadas > 0 else None
        media_ne = round(ne_total / count_disc_avaliadas, 2) if count_disc_avaliadas > 0 else None # NE é contagem, média pode não fazer sentido
        media_npd = round(npd_total / count_disc_avaliadas, 2) if count_disc_avaliadas > 0 else None


        stats = {
            'total_geral': total_geral_filtrado, # Total no período/área
            'total_ce': total_ce_filtrado,
            'acertos_ce': acertos_ce,
            'erros_ce': erros_ce,
            'score_ce': score_ce,
            'percentual_ce': percentual_ce,
            'total_disc': total_disc_filtrado,
            'total_disc_avaliadas': count_disc_avaliadas, # Quantas foram efetivamente avaliadas pela IA
            'media_nc': media_nc,
            'media_ne': media_ne, # Média de erros de português
            'media_npd': media_npd, # Média da nota final discursiva
        }
        logger.info(f"Stats Dashboard (Filtrado) {request.user.username}: {stats}")

        # Pega as últimas 20 DENTRO do período/área filtrado para exibir na lista
        tentativas_recentes = todas_tentativas_qs.order_by('-data_resposta')[:20]

    except Exception as e:
        logger.error(f"Erro ao carregar dados do dashboard para {request.user.username}: {e}", exc_info=True)
        messages.error(request, "Ocorreu um erro ao carregar seu desempenho. Tente novamente mais tarde.")
        tentativas_recentes = []
        stats = {}

    context['tentativas_list'] = tentativas_recentes
    context['stats'] = stats
    # Passa os filtros usados de volta para o template preencher o form
    context['current_date_from'] = date_from_obj
    context['current_date_to'] = date_to_obj
    context['current_area_filter'] = area_filter_obj # Passa o objeto Area
    context['all_areas'] = AreaConhecimento.objects.all().order_by('nome') # Passa todas as áreas para o dropdown do filtro

    return render(request, 'generator/dashboard.html', context)