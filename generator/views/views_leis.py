# generator/views/views_leis.py (ou onde você colocar)
from urllib import request
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse  # Import JsonResponse
from ..models import LeiPlanalto, TipoNormaPlanalto # Ajuste o import se necessário
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify
md_converter = markdownify
#from markdownify import markdownify as md_converter # Renomeado para evitar conflito
import markdown # Biblioteca Python-Markdown
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET
import logging

def listar_leis_coletadas_planalto(request):
    query = request.GET.get('q', '').strip()
    tipo_norma_id = request.GET.get('tipo_norma', '')
    ano_norma_selecionado = request.GET.get('ano_norma', '')

    leis_list = LeiPlanalto.objects.select_related('tipo_norma').all()

    if query:
        leis_list = leis_list.filter(
            Q(titulo_ou_ementa__icontains=query) |
            Q(numero_norma__icontains=query) |
            Q(texto_integral_html__icontains=query) # Cuidado com a performance aqui
        )

    if tipo_norma_id:
        leis_list = leis_list.filter(tipo_norma_id=tipo_norma_id)

    if ano_norma_selecionado:
        leis_list = leis_list.filter(ano_norma=ano_norma_selecionado)

    leis_list = leis_list.order_by('-data_publicacao', '-id')

    paginator = Paginator(leis_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    tipos_norma = TipoNormaPlanalto.objects.all().order_by('nome')

    # AJUSTE AQUI: Linha .exclude(ano_norma__exact='') removida
    anos_norma_disponiveis = LeiPlanalto.objects.filter(ano_norma__isnull=False)\
                                          .values_list('ano_norma', flat=True)\
                                          .distinct()\
                                          .order_by('-ano_norma') # Anos mais recentes primeiro

    context = {
        'page_obj': page_obj,
        'titulo_pagina': "Consulta de Leis e Normas (Planalto)",
        'query': query,
        'tipos_norma': tipos_norma,
        'tipo_norma_selecionado_id': int(tipo_norma_id) if tipo_norma_id and tipo_norma_id.isdigit() else None,
        'anos_norma_disponiveis': anos_norma_disponiveis,
        'ano_norma_selecionado': ano_norma_selecionado,
    }
    return render(request, 'generator/leis_planalto/listar_leis.html', context)

logger = logging.getLogger(__name__)

@require_GET
def extract_and_markdownify_view(request): # <--- CORREÇÃO AQUI! Adicione 'request'
    url = request.GET.get('url')
    if not url:
        return HttpResponseBadRequest("URL não fornecida.")

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao buscar URL '{url}': {e}")
        return JsonResponse({'error': f"Não foi possível buscar o conteúdo da URL: {e}"}, status=500)

    try:
        soup = BeautifulSoup(response.content, 'html.parser')
        content_element = None
        selectors_to_try = [
            'div#textoimpressao',
            'div.textoNorma',
            'article.documento-interno',
            'article',
            'main#content',
            'div.main-content',
            'div[role="main"]'
        ]
        for selector in selectors_to_try:
            content_element = soup.select_one(selector)
            if content_element:
                logger.info(f"Conteúdo encontrado para '{url}' com selector '{selector}'")
                break
        
        if not content_element:
            logger.warning(f"Nenhum seletor específico encontrado para '{url}'. Usando o body e limpando.")
            content_element = soup.body
            if content_element:
                tags_to_remove = ['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', '.noprint', '#menu', '#cabecalho', '#rodape']
                for tag_selector in tags_to_remove:
                    for unwanted_tag in content_element.select(tag_selector):
                        unwanted_tag.decompose()
            else:
                logger.error(f"Corpo (body) não encontrado no HTML da URL '{url}'.")
                return JsonResponse({'error': 'Não foi possível parsear o conteúdo principal da página.'}, status=500)

        if not content_element:
             logger.error(f"Elemento de conteúdo final não pôde ser determinado para '{url}'.")
             return JsonResponse({'error': 'Não foi possível isolar o conteúdo principal da página.'}, status=500)

        html_para_converter = str(content_element)
        markdown_text = md_converter(html_para_converter)
        html_output = markdown.markdown(markdown_text, extensions=['extra', 'nl2br', 'sane_lists'])

        return JsonResponse({'html_content': html_output, 'title': soup.title.string if soup.title else url})

    except Exception as e:
        logger.exception(f"Erro ao processar o conteúdo da URL '{url}': {e}")
        return JsonResponse({'error': f"Ocorreu um erro ao processar o conteúdo da página: {e}"}, status=500)