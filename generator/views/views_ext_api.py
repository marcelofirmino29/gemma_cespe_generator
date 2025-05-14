# generator/views.py
import json
import logging
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
import requests
from generator.models import AreaConhecimento
from .. import scraper_logic

logger = logging.getLogger(__name__)

@login_required
def listar_concursos_view(request):
    context = {}
    concursos_list = []
    error_message = None
    info_message = None

    fonte_dados = request.GET.get('source', 'concursosnobrasil').strip() # Scraper CNB como padrão
    filtro_titulo = request.GET.get('q', '').strip()
    filtro_estado = request.GET.get('estado', '').strip().upper()
    filtro_regiao = request.GET.get('regiao', '').strip().capitalize()

    context['fonte_dados_atual'] = fonte_dados
    context['filtro_ativo'] = None

    if fonte_dados == 'api_vercel': # Mantido desabilitado
        logger.warning("Tentativa de usar a API Vercel, que está reportada como offline.")
        error_message = "A API externa Vercel não está mais disponível. Por favor, utilize outra fonte."

    elif fonte_dados == 'concursosnobrasil':
        logger.info("Usando fonte de dados: ConcursosNoBrasil.com (Scraper)")
        categoria_scraper = 'br' # Padrão Nacional
        if filtro_estado:
            categoria_scraper = filtro_estado.lower()
        
        # Validação e obtenção da URL específica para CNB
        target_url_cnb, err_cat_cnb = scraper_logic.get_target_url_and_validate_category_cnb(categoria_scraper)
        
        if err_cat_cnb:
            error_message = err_cat_cnb
            context['filtro_ativo'] = f"Tentativa: {filtro_estado.upper() if filtro_estado else 'Nacional'} (inválido para CNB)"
        else:
            context['filtro_ativo'] = "Nacional (ConcursosNoBrasil)" if categoria_scraper == 'br' else f"Estado: {categoria_scraper.upper()} (ConcursosNoBrasil)"
            logger.info(f"Iniciando scraper ConcursosNoBrasil para: {target_url_cnb}")
            soup_cnb, err_init_cnb = scraper_logic.init_web_scraper(target_url_cnb)
            
            if err_init_cnb:
                error_message = err_init_cnb
            elif soup_cnb:
                scraped_data_cnb, err_extract_cnb = scraper_logic.extract_concursos_data_cnb(soup_cnb)
                if err_extract_cnb and scraped_data_cnb is None:
                    error_message = err_extract_cnb
                elif scraped_data_cnb:
                    logger.info(f"Recebidos {len(scraped_data_cnb)} concursos do ConcursosNoBrasil.")
                    for item in scraped_data_cnb:
                        if filtro_titulo and filtro_titulo.lower() not in item.get("organizacao", "").lower():
                            continue
                        concursos_list.append({
                            "concurso": item.get("organizacao", "Não informado"),
                            "estado": categoria_scraper.upper() if categoria_scraper != 'br' else "BR",
                            "regiao": "N/A",
                            "detalhes": {
                                "nivel": "Não informado",
                                "vagas": item.get("vagasDisponiveis", "Não informado"),
                                "salario": "Não informado",
                                "periodo_inscricao": "Não informado",
                                "link_inscricao": item.get("link", "#"),
                                "status_cnb": item.get("status", "Não informado")
                            },
                            "origem_concurso": "ConcursosNoBrasil"
                        })
                    if not concursos_list and not error_message:
                        msg = f"Nenhum concurso encontrado no ConcursosNoBrasil para {context['filtro_ativo']}"
                        if filtro_titulo: msg += f" com o título '{filtro_titulo}'"
                        info_message = msg + "."
                    elif err_extract_cnb: info_message = err_extract_cnb
                elif err_extract_cnb : info_message = err_extract_cnb
                else:
                    if not error_message and not info_message:
                        info_message = "Nenhum dado de concurso encontrado na página do ConcursosNoBrasil."
            else:
                error_message = "Falha ao obter conteúdo da página para o scraper ConcursosNoBrasil."
        
        if filtro_regiao and not error_message:
            current_info = info_message if info_message else ""; separator = " " if current_info else ""
            info_message = current_info + separator + "Filtro de Região não é aplicável diretamente à fonte ConcursosNoBrasil."

    elif fonte_dados == 'pciconcursos':
        logger.info("Usando fonte de dados: PCI Concursos (Scraper da Capa)")
        # Para PCI, vamos sempre buscar da página principal (capa de notícias)
        # Filtros de estado e região são apenas informativos para o usuário, não usados na URL de busca do PCI (para capa)
        url_pci = scraper_logic.BASE_URL_PCI 
        context['filtro_ativo'] = "Notícias da Capa (PCI Concursos)"

        if filtro_estado or filtro_regiao:
            # Apenas mensagem informativa, já que o scraper da capa do PCI não usa esses filtros na URL
            current_info = info_message if info_message else ""
            separator = " " if current_info else ""
            info_message = current_info + separator + "Filtros de estado/região não são usados diretamente na busca da capa do PCI. O filtro de Título é aplicado aos resultados."

        soup_pci, err_init_pci = scraper_logic.init_web_scraper(url_pci)
        
        if err_init_pci:
            error_message = err_init_pci
        elif soup_pci:
            scraped_data_pci, err_extract_pci = scraper_logic.extract_concursos_data_pci(soup_pci)

            if err_extract_pci and scraped_data_pci is None: # Erro crítico
                error_message = err_extract_pci
            elif scraped_data_pci:
                logger.info(f"Recebidas {len(scraped_data_pci)} notícias de concursos do PCI.")
                for item in scraped_data_pci:
                    if filtro_titulo and filtro_titulo.lower() not in item.get("organizacao", "").lower():
                        continue
                    concursos_list.append({
                        "concurso": item.get("organizacao", "Título não encontrado"),
                        "estado": item.get("estado_inferido", "N/A"), # PCI capa não especifica estado facilmente
                        "regiao": item.get("regiao_inferida", "N/A"), # PCI capa não especifica região facilmente
                        "detalhes": {
                            "nivel": "Ver detalhes",
                            "vagas": item.get("vagasDisponiveis", "Ver detalhes"),
                            "salario": "Ver detalhes",
                            "periodo_inscricao": "Ver detalhes",
                            "link_inscricao": item.get("link", "#"),
                            "status_pci": item.get("status", "aberto"),
                            "resumo_pci": item.get("resumo", "") 
                        },
                        "origem_concurso": "PCIConcursos"
                    })
                if not concursos_list and not error_message:
                    msg = f"Nenhuma notícia de concurso encontrada na capa do PCI Concursos"
                    if filtro_titulo: msg += f" com o título '{filtro_titulo}'"
                    info_message = msg + "."
                # Se err_extract_pci for "Nenhuma notícia...", já é tratado como info
                elif err_extract_pci and "Nenhuma notícia de concurso encontrada" in err_extract_pci : info_message = err_extract_pci

            elif err_extract_pci: # scraped_data_pci é None ou [] E houve err_extract
                if "Nenhuma notícia de concurso encontrada" in err_extract_pci: info_message = err_extract_pci
                else: error_message = err_extract_pci
            else:
                if not error_message and not info_message:
                    info_message = "Nenhum dado de concurso (notícias) encontrado na capa do PCI Concursos."
        else: # soup é None
            error_message = "Falha ao obter conteúdo da página do PCI Concursos."

    # --- Paginação ---
    items_per_page = 15
    mypaginator = Paginator(concursos_list, items_per_page)
    page_number = request.GET.get('page')
    try:
        page_obj = mypaginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = mypaginator.get_page(1)
    except EmptyPage:
        page_obj = mypaginator.get_page(mypaginator.num_pages)

    # --- Contexto Final ---
    context['page_obj'] = page_obj
    context['paginator'] = mypaginator
    context['error_message'] = error_message
    context['info_message'] = info_message
    context['filtro_titulo_atual'] = filtro_titulo
    context['filtro_estado_atual'] = filtro_estado
    context['filtro_regiao_atual'] = filtro_regiao
    context['regioes_validas'] = ['Norte', 'Nordeste', 'Sul', 'Sudeste', 'Centro-oeste']

    if 'all_areas' not in context:
        try:
            context['all_areas'] = AreaConhecimento.objects.all().order_by('nome')
        except Exception as e:
            logger.error(f"Erro buscar AreaConhecimento: {e}")

    return render(request, 'generator/listar_concursos.html', context)