import json
from venv import logger
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
import requests
from generator.models import AreaConhecimento

@login_required
def listar_concursos_view(request):
    context = {}
    concursos_list = []
    error_message = None
    api_base_url = "https://concursos-publicos-api.vercel.app/api"

    # --- Filtros ---
    filtro_titulo = request.GET.get('q', '').strip()
    filtro_estado = request.GET.get('estado', '').strip().upper()
    filtro_regiao = request.GET.get('regiao', '').strip().capitalize()

    # --- Monta URL ---
    api_url = api_base_url
    params = {} # Para futura expansão se a API aceitar query params

    if filtro_titulo:
        api_url = f"{api_base_url}/titulo/{filtro_titulo}"
        context['filtro_ativo'] = filtro_titulo
    elif filtro_estado:
        if len(filtro_estado) == 2 and filtro_estado.isalpha():
            api_url = f"{api_base_url}/estado/{filtro_estado}"
            context['filtro_ativo'] = f"Estado: {filtro_estado}"
        else:
            error_message = "Sigla de estado inválida."; api_url = None; filtro_estado = ''
    elif filtro_regiao:
        regioes_validas = ['Norte', 'Nordeste', 'Sul', 'Sudeste', 'Centro-oeste']
        api_filtro_regiao = next((r for r in regioes_validas if r.lower() == filtro_regiao.lower()), None)
        if api_filtro_regiao:
             # A API parece usar 'Centro-Oeste', ajuste se necessário
             api_url_regiao = 'Centro-Oeste' if api_filtro_regiao.lower() == 'centro-oeste' else api_filtro_regiao
             api_url = f"{api_base_url}/regiao/{api_url_regiao}"
             context['filtro_ativo'] = f"Região: {api_filtro_regiao}"
        else:
            error_message = "Região inválida."; api_url = None; filtro_regiao = ''
    else:
        # Busca Sudeste por padrão para não sobrecarregar
        api_url = f"{api_base_url}/regiao/Sudeste"
        context['filtro_ativo'] = "Região: Sudeste (padrão)"; filtro_regiao = 'Sudeste'

    # --- Chama API ---
    if api_url:
        try:
            logger.info(f"Chamando API externa de concursos: {api_url}")
            # VV CORREÇÃO 1: usar requests.get VV
            response = requests.get(api_url, timeout=15)
            response.raise_for_status()
            concursos_data = response.json()

            if isinstance(concursos_data, list):
                concursos_list = concursos_data
                logger.info(f"Recebidos {len(concursos_list)} concursos.")
            else:
                logger.warning(f"API retornou formato inesperado: {type(concursos_data)}")
                error_message = "API externa retornou dados em formato inesperado."

        # VV CORREÇÃO 2: usar requests.exceptions.Timeout VV
        except requests.exceptions.Timeout:
            logger.error(f"Timeout ao chamar API: {api_url}")
            error_message = "Busca por concursos demorou muito. Tente novamente."
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro conexão/HTTP API: {e}")
            error_message = f"Erro ao conectar com API de concursos: Verifique a URL ou a API pode estar offline."
        except json.JSONDecodeError:
            logger.error(f"Erro decodificar JSON API: {api_url}")
            error_message = "API externa retornou resposta inválida."
        except Exception as e:
            logger.error(f"Erro inesperado API concursos: {e}", exc_info=True)
            error_message = "Erro inesperado ao buscar concursos."

    # --- Paginação ---
    items_per_page = 15
    paginator = paginator(concursos_list, items_per_page)
    page_number = request.GET.get('page')
    try: page_obj = paginator.get_page(page_number)
    except PageNotAnInteger: page_obj = paginator.get_page(1)
    except EmptyPage: page_obj = paginator.get_page(paginator.num_pages)

    # --- Contexto Final ---
    context['page_obj'] = page_obj
    context['paginator'] = paginator
    context['error_message'] = error_message
    context['filtro_titulo_atual'] = filtro_titulo
    context['filtro_estado_atual'] = filtro_estado
    context['filtro_regiao_atual'] = filtro_regiao
    context['regioes_validas'] = ['Norte', 'Nordeste', 'Sul', 'Sudeste', 'Centro-oeste']

    # Busca Areas para o filtro (se ainda não tiver)
    if 'all_areas' not in context: # Evita buscar se já veio de outra parte do contexto base
        try: context['all_areas'] = AreaConhecimento.objects.all().order_by('nome')
        except Exception as e: logger.error(f"Erro buscar AreaConhecimento: {e}")

    return render(request, 'generator/listar_concursos.html', context)