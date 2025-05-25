# generator/views.py
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Coalesce
from ..models import ProvaPCIConcurso # Importe o modelo que criamos

def listar_provas_coletadas(request):
    provas_queryset = ProvaPCIConcurso.objects.select_related(
        'orgao', 'banca', 'nivel_escolaridade', 'cargo'
    ).all()

    # --- Obter valores para os dropdowns dos filtros ---
    # Usamos .values_list() para obter uma lista de tuplas e flat=True para uma lista simples.
    # distinct() garante valores únicos. order_by() para ordenação.
    # Coalesce é usado para tratar casos onde o campo relacionado (FK) pode ser NULL,
    # e assim não quebrar o values_list ou distinct em alguns bancos.
    # Se você tem certeza que os campos FK nunca são NULL ou não quer incluir provas sem esses dados,
    # pode simplificar um pouco.

    # Opções para Órgão
    orgaos_disponiveis = ProvaPCIConcurso.objects.filter(orgao__nome__isnull=False)\
        .values_list('orgao__nome', flat=True).distinct().order_by('orgao__nome')

    # Opções para Banca
    bancas_disponiveis = ProvaPCIConcurso.objects.filter(banca__nome__isnull=False)\
        .values_list('banca__nome', flat=True).distinct().order_by('banca__nome')

    # Opções para Ano (considerando apenas anos presentes nas provas)
    anos_disponiveis = ProvaPCIConcurso.objects.filter(ano__isnull=False)\
        .values_list('ano', flat=True).distinct().order_by('-ano') # Mais recentes primeiro

    # Opções para Nível (combinando de FK e campo de texto, se necessário)
    niveis_fk = ProvaPCIConcurso.objects.filter(nivel_escolaridade__nome__isnull=False)\
        .values_list('nivel_escolaridade__nome', flat=True)
    niveis_texto = ProvaPCIConcurso.objects.filter(nivel_detalhado_texto__isnull=False)\
        .exclude(nivel_detalhado_texto__exact='')\
        .values_list('nivel_detalhado_texto', flat=True)
    niveis_disponiveis = sorted(list(set(list(niveis_fk) + list(niveis_texto))))


    # Opções para Cargo (similar ao Nível, pode vir de FK ou texto)
    cargos_fk = ProvaPCIConcurso.objects.filter(cargo__nome__isnull=False)\
        .values_list('cargo__nome', flat=True)
    cargos_texto = ProvaPCIConcurso.objects.filter(categoria_cargo_principal_texto__isnull=False)\
        .exclude(categoria_cargo_principal_texto__exact='')\
        .values_list('categoria_cargo_principal_texto', flat=True)
    cargos_disponiveis = sorted(list(set(list(cargos_fk) + list(cargos_texto))))


    # --- LÓGICA DE FILTRAGEM ---
    q_concurso_raw = request.GET.get('q_concurso', '') # Usar '' como default
    orgao_selecionado = request.GET.get('orgao', '')
    cargo_selecionado = request.GET.get('cargo', '')
    banca_selecionada = request.GET.get('banca', '')
    ano_selecionado_str = request.GET.get('ano', '')
    nivel_selecionado = request.GET.get('nivel', '')

    # Limpar espaços para campos de texto livre
    q_concurso = q_concurso_raw.strip()

    if q_concurso:
        provas_queryset = provas_queryset.filter(
            Q(nome_concurso_detalhado__icontains=q_concurso) |
            Q(titulo_link_origem__icontains=q_concurso)
        )
    if orgao_selecionado: # Checa se não é string vazia
        provas_queryset = provas_queryset.filter(orgao__nome__iexact=orgao_selecionado) # Usar iexact para dropdown
    if cargo_selecionado:
        provas_queryset = provas_queryset.filter(
            Q(cargo__nome__iexact=cargo_selecionado) |
            Q(categoria_cargo_principal_texto__iexact=cargo_selecionado)
        )
    if banca_selecionada:
        provas_queryset = provas_queryset.filter(banca__nome__iexact=banca_selecionada) # Usar iexact para dropdown
    if ano_selecionado_str:
        try:
            ano = int(ano_selecionado_str)
            provas_queryset = provas_queryset.filter(ano=ano)
        except ValueError:
            pass # Ignora se não for um ano válido
    if nivel_selecionado:
        provas_queryset = provas_queryset.filter(
            Q(nivel_escolaridade__nome__iexact=nivel_selecionado) |
            Q(nivel_detalhado_texto__iexact=nivel_selecionado)
        )

    provas_list_filtrada_e_ordenada = provas_queryset.order_by('ano', 'orgao__nome')

# ... (seu código de filtragem e ordenação fica acima desta parte)
    # provas_list_filtrada_e_ordenada = provas_queryset.order_by('ano__isnull', '-ano', 'orgao__nome')

    paginator = Paginator(provas_list_filtrada_e_ordenada, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'titulo_pagina': "Provas de Concursos Coletadas (PCI)",
        # Passando as listas de opções para os filtros (correto para os dropdowns)
        'orgaos_disponiveis': orgaos_disponiveis,
        'bancas_disponiveis': bancas_disponiveis,
        'anos_disponiveis': anos_disponiveis, # Esta lista já deve estar ordenada como você deseja para o dropdown (ex: -ano)
        'niveis_disponiveis': niveis_disponiveis,
        'cargos_disponiveis': cargos_disponiveis,

        # Passando os valores selecionados para re-selecionar nos forms
        # request.GET já está disponível no template, mas pode ser explícito se preferir.
        # 'q_concurso_val': q_concurso_raw,
        # 'orgao_selecionado_val': orgao_selecionado,
        # 'cargo_selecionado_val': cargo_selecionado,
        # 'banca_selecionada_val': banca_selecionada,
        # 'ano_selecionado_val': ano_selecionado_str,
        # 'nivel_selecionado_val': nivel_selecionado,
    }
    return render(request, 'generator/listar_provas_pci.html', context)