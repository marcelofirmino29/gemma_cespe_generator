import re
import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urljoin, urlparse

# --- Constantes do PCIConcursos.com.br ---
BASE_URL_PCI = "https://www.pciconcursos.com.br/"
PROVAS_URL_RAIZ_PCI = urljoin(BASE_URL_PCI, "/provas/")
SITE_DOMAIN_PCI = "https://www.pciconcursos.com.br"

# --- Funções Genéricas de Requisição e Inicialização ---
def page_request(url: str):
    """
    Faz uma requisição GET para a URL fornecida.
    Retorna o objeto de resposta e uma mensagem de erro (se houver).
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response, None
    except requests.exceptions.HTTPError as http_err:
        error_message = f"Erro HTTP ao acessar {url}: {http_err}"
        print(error_message)
        return None, error_message
    except requests.exceptions.ConnectionError as conn_err:
        error_message = f"Erro de conexão ao acessar {url}: {conn_err}"
        print(error_message)
        return None, error_message
    except requests.exceptions.Timeout as timeout_err:
        error_message = f"Timeout ao acessar {url}: {timeout_err}"
        print(error_message)
        return None, error_message
    except requests.exceptions.RequestException as req_err:
        error_message = f"Erro na requisição para {url}: {req_err}"
        print(error_message)
        return None, error_message
    except Exception as e:
        error_message = f"Ocorreu um erro inesperado durante a requisição para {url}: {e}"
        print(error_message)
        return None, error_message

def init_web_scraper(url: str, parser: str = 'html.parser'):
    """
    Inicializa o scraper: faz a requisição e parseia o HTML.
    Retorna o objeto BeautifulSoup e uma mensagem de erro (se houver).
    """
    web_response, error = page_request(url)
    if error:
        return None, error
    if web_response is None:
        return None, f"Resposta da página foi nula para {url} (sem erro explícito de request)."
    try:
        soup = BeautifulSoup(web_response.content, parser)
        return soup, None
    except Exception as e:
        error_message = f"Erro ao parsear o HTML de {url}: {e}"
        print(error_message)
        return None, error_message

# --- Funções Específicas para Scraper de PROVAS do PCIConcursos.com.br ---

def extrair_links_de_categorias_de_provas(url_raiz_provas):
    """
    Extrai os links para as diversas categorias de provas (por cargo) da página principal de provas.
    """
    print(f"Buscando categorias de provas em: {url_raiz_provas}")
    soup, error = init_web_scraper(url_raiz_provas)
    if error:
        print(f"Não foi possível buscar categorias: {error}")
        return []

    categorias_encontradas = []
    container_principal_provas = soup.find('div', id='provas')
    if not container_principal_provas:
        print("Container principal 'div#provas' não encontrado.")
        return []

    lista_ul = None
    h2_provas_cargo = container_principal_provas.find('h2', string=re.compile(r"Provas por Cargo", re.IGNORECASE))
    if h2_provas_cargo:
        lista_ul = h2_provas_cargo.find_next_sibling('ul', class_='link-i')
    
    if not lista_ul:
        div_com_estilo_especifico = container_principal_provas.find('div', style=re.compile(r"margin-left:10px", re.IGNORECASE))
        if div_com_estilo_especifico:
            lista_ul = div_com_estilo_especifico.find('ul', class_='link-i')

    if not lista_ul:
        lista_ul = container_principal_provas.find('ul', class_='link-i')

    if not lista_ul:
        print("Lista de categorias de provas ('ul.link-i') não encontrada após todas as tentativas.")
        return []

    for li_tag in lista_ul.find_all('li', recursive=False):
        a_tag = li_tag.find('a', href=True)
        if a_tag:
            nome_categoria = a_tag.text.strip()
            href_value = a_tag['href']
            
            is_valid_category_link = False
            url_categoria_final = None
            path_part = None

            if href_value.startswith(SITE_DOMAIN_PCI):
                if href_value.startswith(SITE_DOMAIN_PCI + '/provas/'):
                    path_part = href_value.replace(SITE_DOMAIN_PCI, "")
                    url_categoria_final = href_value
            elif href_value.startswith('/provas/'):
                path_part = href_value
                url_categoria_final = urljoin(BASE_URL_PCI, href_value)
            
            if path_part:
                path_segments = path_part.split('/')
                if len(path_segments) > 2 and path_segments[1] == 'provas' and path_segments[-1]: 
                    is_valid_category_link = True
            
            if is_valid_category_link:
                if url_categoria_final and url_categoria_final.rstrip('/') != PROVAS_URL_RAIZ_PCI.rstrip('/'):
                    categorias_encontradas.append({
                        "nome_categoria": nome_categoria,
                        "url_categoria": url_categoria_final
                    })
    
    print(f"Total de {len(categorias_encontradas)} categorias de cargo encontradas.")
    if len(categorias_encontradas) > 0:
        print(f"  Exemplo de categoria encontrada: {categorias_encontradas[0]['nome_categoria']} - {categorias_encontradas[0]['url_categoria']}")
    return categorias_encontradas

def extrair_infos_preliminares_do_texto_link(texto_link, nome_categoria_cargo):
    partes = [p.strip() for p in texto_link.split('-')]
    orgao = partes[0] if len(partes) > 0 else nome_categoria_cargo
    match_ano = re.search(r'\b(20\d{2})\b', texto_link)
    ano = match_ano.group(1) if match_ano else "Não definido"
    banca = "Não definida" 
    cargo = nome_categoria_cargo 
    if len(partes) > 1:
        detalhes_restantes = " - ".join(partes[1:]) 
        detalhes_restantes = re.sub(r'\b(20\d{2})\b', '', detalhes_restantes, flags=re.IGNORECASE).strip()
        detalhes_restantes = re.sub(r'\((Prova|Gabarito|Prova e Gabarito|Caderno de Questões|Edital)\s*\d*\)', '', detalhes_restantes, flags=re.IGNORECASE).strip()
        detalhes_restantes = re.sub(r'Prova e Gabarito|Prova|Gabarito|Caderno de Questões|Edital', '', detalhes_restantes, flags=re.IGNORECASE).strip().strip('-').strip()
        if detalhes_restantes and len(detalhes_restantes) > 2 : 
            bancas_comuns_keywords = ['CESPE', 'CEBRASPE', 'FGV', 'FCC', 'VUNESP', 'IBFC', 'AOCP', 'CONSULPLAN', 'IBADE', 'QUADRIX', 'IDECAN', 'CESGRANRIO', 'FUNDATEC', 'FADESP'] 
            for keyword_banca in bancas_comuns_keywords:
                if re.search(r'\b' + re.escape(keyword_banca) + r'\b', detalhes_restantes, re.IGNORECASE):
                    banca = keyword_banca 
                    detalhes_restantes = re.sub(r'\b' + re.escape(keyword_banca) + r'\b', '', detalhes_restantes, flags=re.IGNORECASE).strip().strip('-').strip()
                    break
            if detalhes_restantes: 
                cargo = f"{nome_categoria_cargo} - {detalhes_restantes}"
    return orgao, cargo, banca, ano

def extrair_detalhes_pagina_download(soup_detalhes, url_pagina_download):
    dados_prova = {
        "nome_concurso_detalhado": "Não encontrado", "cargo_detalhado": "Não encontrado",
        "ano_detalhado": "Não encontrado", "orgao_detalhado": "Não encontrado",
        "instituicao_detalhada": "Não encontrado", "nivel_detalhado": "Não encontrado",
        "url_prova_pdf": None, "url_gabarito_pdf": None
    }
    cards = soup_detalhes.find_all('div', class_='card')
    card_detalhes_prova = None
    for card in cards:
        header = card.find('div', class_='card-header')
        if header:
            h5_tag = header.find('h5', class_='text-pci')
            if h5_tag and "prova" in h5_tag.text.lower(): 
                 if not re.search(r"(visualizar|download) os arquivos pdf", h5_tag.text, re.IGNORECASE):
                    card_detalhes_prova = card
                    break
    if card_detalhes_prova:
        h5_title = card_detalhes_prova.find('div', class_='card-header').find('h5', class_='text-pci')
        if h5_title:
            dados_prova["nome_concurso_detalhado"] = h5_title.text.replace("Prova ", "").strip()
        list_items = card_detalhes_prova.find_all('li', class_='mb-2')
        for item in list_items:
            strong_tag = item.find('strong')
            div_container_valor = item.find('div', class_=lambda x: x != 'mr-3 text-center text-pci' if x else True) 
            if strong_tag and div_container_valor:
                key = strong_tag.text.strip().lower()
                value_tag = div_container_valor.find(['a', 'span'], class_='text-pci')
                value = ""
                if value_tag: value = value_tag.text.strip()
                else: 
                    all_text_parts = [s.strip() for s in div_container_valor.find_all(string=True, recursive=True) if s.strip()]
                    value = " ".join(part for part in all_text_parts if strong_tag.text.strip() not in part).strip()
                if 'cargo:' in key: dados_prova["cargo_detalhado"] = value
                elif 'ano:' in key: dados_prova["ano_detalhado"] = value
                elif 'órgão:' in key: dados_prova["orgao_detalhado"] = value
                elif 'instituição:' in key: dados_prova["instituicao_detalhada"] = value
                elif 'nível:' in key: dados_prova["nivel_detalhado"] = value
    else:
        title_tag = soup_detalhes.find('title')
        if title_tag: dados_prova["nome_concurso_detalhado"] = title_tag.text.replace("Provas para Download -", "").strip()

    card_links_pdf = None
    for card in cards:
        header = card.find('div', class_='card-header')
        if header:
            h5_tag = header.find('h5', class_='text-pci')
            if h5_tag and re.search(r"(visualizar|download) os arquivos pdf", h5_tag.text, re.IGNORECASE):
                card_links_pdf = card; break
    if card_links_pdf:
        pdf_items = card_links_pdf.find_all('div', class_='pdf-item')
        for pdf_item in pdf_items:
            link_tag = pdf_item.find('a', class_='item-link', href=True)
            pdf_text_span = pdf_item.find('span', class_='text-pci') 
            if link_tag and pdf_text_span:
                href_pdf = link_tag['href']
                nome_arquivo_pdf = pdf_text_span.text.lower() 
                texto_link_associado = link_tag.text.lower() 
                if not href_pdf.startswith('http'): href_pdf = urljoin(url_pagina_download, href_pdf)
                is_prova = 'prova' in texto_link_associado or 'caderno' in texto_link_associado or 'enunciado' in texto_link_associado or \
                           'prova' in nome_arquivo_pdf or 'caderno' in nome_arquivo_pdf
                is_gabarito = 'gabarito' in texto_link_associado or 'respostas' in texto_link_associado or \
                              'gabarito' in nome_arquivo_pdf
                if is_prova and not dados_prova["url_prova_pdf"]: dados_prova["url_prova_pdf"] = href_pdf
                elif is_gabarito and not dados_prova["url_gabarito_pdf"]: dados_prova["url_gabarito_pdf"] = href_pdf
        if not dados_prova["url_prova_pdf"] and not dados_prova["url_gabarito_pdf"] and len(pdf_items) == 1:
            link_tag = pdf_items[0].find('a', class_='item-link', href=True)
            if link_tag: dados_prova["url_prova_pdf"] = urljoin(url_pagina_download, link_tag['href'])
        elif not dados_prova["url_prova_pdf"] and len(pdf_items) > 0: 
            for pdf_item in pdf_items:
                link_tag = pdf_item.find('a', class_='item-link', href=True)
                pdf_text_span = pdf_item.find('span', class_='text-pci')
                if link_tag and pdf_text_span:
                    href_pdf_fallback = urljoin(url_pagina_download, link_tag['href'])
                    if href_pdf_fallback != dados_prova["url_gabarito_pdf"]: 
                        dados_prova["url_prova_pdf"] = href_pdf_fallback; break
    return dados_prova

def eh_pagina_de_download_final(url_absoluta):
    """Verifica se a URL parece ser uma página final de download de prova."""
    parsed_url = urlparse(url_absoluta)
    path_segments = [s for s in parsed_url.path.split('/') if s]
    # Padrões: /provas/download/... ou /provas/ID_NUMERICO/...
    if len(path_segments) >= 2 and path_segments[0] == 'provas':
        if path_segments[1] == 'download' and len(path_segments) > 2:
            return True
        if path_segments[1].isdigit() and len(path_segments) > 2 : # Ex: /provas/123456/nome-da-prova
             # Adicionalmente, verificar se o último segmento não é 'pagina' (caso de ID ser usado para banca/órgão)
            if path_segments[-1] != 'pagina' and (len(path_segments) < 4 or path_segments[-2] != 'pagina'):
                return True
    return False

def eh_link_de_sublistagem_valido(url_absoluta, url_pagina_atual, links_visitados_geral):
    """Verifica se um link deve ser seguido recursivamente."""
    if url_absoluta in links_visitados_geral:
        return False
    
    parsed_url = urlparse(url_absoluta)
    path = parsed_url.path

    # Deve estar dentro da seção de provas
    if not path.startswith('/provas/'):
        return False
    
    # Não seguir links de paginação aqui (tratados no loop principal)
    if '/pagina/' in path:
        return False
        
    # Não seguir links que são claramente para arquivos (tratados na página de download)
    if path.lower().endswith(('.pdf', '.zip', '.doc', '.docx')):
        return False

    # Não seguir links de utilidade da seção de provas
    if any(util_path in path for util_path in ['/provas/top', '/provas/colaborar', '/provas/organizadoras']):
        return False

    # Evitar voltar para a raiz de /provas/ ou a própria página
    if url_absoluta.rstrip('/') == PROVAS_URL_RAIZ_PCI.rstrip('/') or url_absoluta == url_pagina_atual:
        return False

    # Se passou por todos os filtros acima e não é uma página de download final, é uma sublistagem válida.
    if not eh_pagina_de_download_final(url_absoluta):
        return True
        
    return False


def extrair_provas_de_pagina_listagem(url_pagina_listagem, nome_categoria_cargo, links_visitados_geral, current_depth=0, max_depth=2):
    """
    Extrai informações das provas listadas em uma página ou segue links para sub-listagens/páginas de download.
    Modificada para ser recursiva.
    """
    if url_pagina_listagem in links_visitados_geral and current_depth > 0 : # Evita reprocessar a mesma URL na recursão
        # print(f"    DEBUG: URL já visitada nesta sessão de scraping: {url_pagina_listagem}")
        return []
    
    links_visitados_geral.add(url_pagina_listagem) # Marca como visitada

    print(f"  Analisando (Profundidade: {current_depth}): {url_pagina_listagem} (Categoria Base: '{nome_categoria_cargo}')")
    
    if current_depth > max_depth:
        print(f"    Profundidade máxima de recursão ({max_depth}) atingida para {url_pagina_listagem}")
        return []

    soup, error = init_web_scraper(url_pagina_listagem)
    if error:
        print(f"    Erro ao raspar página {url_pagina_listagem}: {error}")
        return []

    provas_coletadas_nesta_chamada = []
    
    conteudo_principal = soup.find('div', id='conteudo')
    elementos_para_buscar_links = soup 
    if conteudo_principal:
        caixa_conteudo = conteudo_principal.find('div', class_='caixa_conteudo_pc') 
        elementos_para_buscar_links = caixa_conteudo if caixa_conteudo else conteudo_principal
    
    links_tags_encontradas = elementos_para_buscar_links.find_all('a', href=True)
    
    if not links_tags_encontradas:
        # print(f"    Nenhum link <a> com href encontrado nos containers de {url_pagina_listagem}")
        return []

    for link_tag in links_tags_encontradas:
        href_link = link_tag['href']
        texto_link = link_tag.text.strip()
        url_absoluta_link = urljoin(BASE_URL_PCI, href_link)

        # Filtros básicos para ignorar links claramente irrelevantes
        if any(nav_keyword in url_absoluta_link.lower() for nav_keyword in ['javascript:', 'mailto:', '#']) or \
           url_absoluta_link.endswith(('.png', '.jpg', '.gif', '.css', '.js', '.xml', '.ico')):
            continue
        if len(texto_link) < 5: # Links muito curtos geralmente não são o que procuramos
            continue
        if link_tag.find_parent(id=re.compile(r'(menu|footer|header|sidebar|lateral|share|ads|social|rodape|topo|breadcrumbs)', re.IGNORECASE)) or \
           link_tag.find_parent(class_=re.compile(r'(menu|footer|header|sidebar|lateral|share|ads|social|nav|breadcrumb|pagination|paginacao|btn|nav-item|sharelink|widget)', re.IGNORECASE)):
            continue


        if eh_pagina_de_download_final(url_absoluta_link):
            if url_absoluta_link not in links_visitados_geral: # Processa apenas se não foi processada como download antes
                links_visitados_geral.add(url_absoluta_link) # Marca como visitada para download
                print(f"    Página de download final encontrada: '{texto_link}' -> {url_absoluta_link}")
                
                orgao_preliminar, cargo_preliminar, banca_preliminar, ano_preliminar = \
                    extrair_infos_preliminares_do_texto_link(texto_link, nome_categoria_cargo)

                soup_detalhes, err_detalhes = init_web_scraper(url_absoluta_link)
                if err_detalhes:
                    print(f"      Erro ao acessar página de download {url_absoluta_link}: {err_detalhes}")
                    provas_coletadas_nesta_chamada.append({
                        "titulo_link_origem": texto_link, "nome_concurso_detalhado": orgao_preliminar,
                        "orgao": orgao_preliminar, "cargo": cargo_preliminar, "banca": banca_preliminar, "ano": ano_preliminar,
                        "url_pagina_detalhes": url_absoluta_link, "url_prova_pdf": "Erro ao buscar detalhes",
                        "url_gabarito_pdf": "Erro ao buscar detalhes", "fonte": "PCI Concursos",
                        "categoria_cargo_principal": nome_categoria_cargo
                    })
                    time.sleep(1)
                    continue

                dados_download_page = extrair_detalhes_pagina_download(soup_detalhes, url_absoluta_link)

                if dados_download_page["url_prova_pdf"]: 
                    provas_coletadas_nesta_chamada.append({
                        "titulo_link_origem": texto_link,
                        "nome_concurso_detalhado": dados_download_page.get("nome_concurso_detalhado", orgao_preliminar),
                        "orgao": dados_download_page.get("orgao_detalhado", orgao_preliminar),
                        "cargo": dados_download_page.get("cargo_detalhado", cargo_preliminar),
                        "banca": dados_download_page.get("instituicao_detalhada", banca_preliminar), 
                        "ano": dados_download_page.get("ano_detalhado", ano_preliminar),
                        "nivel": dados_download_page.get("nivel_detalhado", "Não definido"),
                        "url_pagina_detalhes": url_absoluta_link,
                        "url_prova_pdf": dados_download_page["url_prova_pdf"],
                        "url_gabarito_pdf": dados_download_page.get("url_gabarito_pdf", "Não encontrado"),
                        "fonte": "PCI Concursos",
                        "categoria_cargo_principal": nome_categoria_cargo
                    })
                time.sleep(1.5)

        elif eh_link_de_sublistagem_valido(url_absoluta_link, url_pagina_listagem, links_visitados_geral):
            print(f"    Navegando para sub-listagem: '{texto_link}' -> {url_absoluta_link}")
            provas_recursivas = extrair_provas_de_pagina_listagem(
                url_absoluta_link,
                nome_categoria_cargo, # Mantém a categoria original para referência, ou pode tentar inferir subcategoria
                links_visitados_geral, # Passa o conjunto de links visitados
                current_depth + 1,
                max_depth
            )
            if provas_recursivas:
                provas_coletadas_nesta_chamada.extend(provas_recursivas)
        # else:
            # print(f"    DEBUG: Link ignorado (não download, não sub-listagem válida, ou já visitado): {url_absoluta_link} (Texto: {texto_link})")
            
    return provas_coletadas_nesta_chamada


def scraper_pci_provas_principal(max_categorias_cargo=5, max_paginas_por_categoria=2, ano_alvo=None, max_profundidade_recursao=2):
    """
    Função principal para orquestrar o scraping de provas do PCI Concursos.
    """
    print("Iniciando Scraper de Provas do PCI Concursos...")
    if ano_alvo:
        print(f"Tentando focar em provas do ano: {ano_alvo}.")

    links_categorias = extrair_links_de_categorias_de_provas(PROVAS_URL_RAIZ_PCI)
    
    if not links_categorias:
        print("Nenhuma categoria de prova encontrada. Encerrando.")
        return []

    todas_as_provas_coletadas = []
    links_visitados_globalmente = set() # Para evitar reprocessar a mesma URL em toda a sessão de scraping
    
    categorias_processadas_count = 0
    for categoria in links_categorias:
        if categorias_processadas_count >= max_categorias_cargo:
            print(f"Limite de {max_categorias_cargo} categorias para processar atingido.")
            break
        
        print(f"\nProcessando Categoria: {categoria['nome_categoria']} ({categoria['url_categoria']})")
        
        for num_pagina in range(1, max_paginas_por_categoria + 1):
            url_listagem_atual = categoria['url_categoria']
            url_base_categoria_com_barra = categoria['url_categoria']
            if not url_base_categoria_com_barra.endswith('/'):
                url_base_categoria_com_barra += '/'
            
            if num_pagina > 1:
                url_listagem_atual = urljoin(url_base_categoria_com_barra, f"pagina/{num_pagina}/")
            
            # print(f"  Analisando página {num_pagina} da categoria: {url_listagem_atual}")
            
            # A chamada inicial para extrair_provas_de_pagina_listagem começa com profundidade 0
            provas_desta_pagina_e_recursao = extrair_provas_de_pagina_listagem(
                url_listagem_atual, 
                categoria['nome_categoria'],
                links_visitados_globalmente, # Passa o conjunto global
                current_depth=0,
                max_depth=max_profundidade_recursao 
            )
            
            if not provas_desta_pagina_e_recursao and num_pagina > 1:
                # print(f"    Nenhuma prova encontrada em {url_listagem_atual} (página > 1) ou suas sub-listagens, possivelmente fim da paginação para esta categoria.")
                break 
            
            if provas_desta_pagina_e_recursao:
                provas_para_adicionar = provas_desta_pagina_e_recursao
                if ano_alvo:
                    provas_filtradas_ano = [
                        p for p in provas_desta_pagina_e_recursao if 
                        str(p.get("ano", "")).strip() == str(ano_alvo).strip() or 
                        str(p.get("ano_inferido", "")).strip() == str(ano_alvo).strip() or
                        str(p.get("ano_detalhado", "")).strip() == str(ano_alvo).strip()
                    ]
                    if len(provas_filtradas_ano) < len(provas_desta_pagina_e_recursao):
                        print(f"    Filtradas {len(provas_filtradas_ano)} provas para o ano {ano_alvo} de {len(provas_desta_pagina_e_recursao)} encontradas (incluindo recursão).")
                    provas_para_adicionar = provas_filtradas_ano
                
                todas_as_provas_coletadas.extend(provas_para_adicionar)

            if not provas_desta_pagina_e_recursao and num_pagina == 1:
                 print(f"    Nenhuma prova encontrada na primeira página ({url_listagem_atual}) da categoria {categoria['nome_categoria']} ou em suas sub-listagens.")
                 break 

            if num_pagina < max_paginas_por_categoria and provas_desta_pagina_e_recursao: 
                time.sleep(2) 
        
        categorias_processadas_count += 1
        if categorias_processadas_count < max_categorias_cargo and categorias_processadas_count < len(links_categorias) : 
             time.sleep(3) 

    if todas_as_provas_coletadas:
        nome_arquivo = "dados_provas_pciconcursos_completo.json"
        if ano_alvo:
            nome_arquivo = f"dados_provas_pciconcursos_{ano_alvo}.json"
        
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(todas_as_provas_coletadas, f, ensure_ascii=False, indent=4)
        print(f"\nTotal de {len(todas_as_provas_coletadas)} provas coletadas e salvas em '{nome_arquivo}'")
    else:
        print("\nNenhuma prova foi coletada com os critérios atuais.")
        
    return todas_as_provas_coletadas

# --- Para Executar o Scraper ---
if __name__ == '__main__':
    dados = scraper_pci_provas_principal(
        max_categorias_cargo=1, 
        max_paginas_por_categoria=1, # Processa apenas a primeira página de cada categoria principal
        ano_alvo="2023",
        max_profundidade_recursao=1 # Limita a profundidade da navegação em sublinks
    ) 
    
    if dados:
        print("\n--- Amostra de Provas Coletadas ---")
        for i, prova_info in enumerate(dados[:min(3, len(dados))]): 
            print(json.dumps(prova_info, indent=2, ensure_ascii=False))
            if i < min(3, len(dados)) -1 : print("---")

