# generator/scraper_logic.py
import requests
from bs4 import BeautifulSoup
import re # Para tentar extrair vagas do PCI

# --- Constantes para ConcursosNoBrasil.com ---
AVAILABLE_CATEGORIES_CNB = ['br', 'ac', 'al', 'am', 'ap', 'ba', 'ce', 'df', 'es', 'go', 'ma', 'mg',
                            'ms', 'mt', 'pa', 'pb', 'pe', 'pi', 'pr', 'rj', 'rn', 'ro', 'rr', 'rs', 'sc', 'se', 'sp', 'to']
BASE_URL_CNB = 'https://concursosnobrasil.com/concursos/'
SITE_DOMAIN_CNB = 'https://concursosnobrasil.com'

# --- Constantes para PCIConcursos.com.br ---
BASE_URL_PCI = "https://www.pciconcursos.com.br/" # Página principal para notícias
# Para raspagem por estado/região no PCI, as URLs seriam diferentes, ex:
# BASE_URL_PCI_ESTADO = "https://www.pciconcursos.com.br/concursos/estado/{}/"
# BASE_URL_PCI_NACIONAL = "https://www.pciconcursos.com.br/concursos/nacional/"
SITE_DOMAIN_PCI = "https://www.pciconcursos.com.br"


# --- Funções Genéricas de Requisição e Inicialização ---
def page_request(url: str):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
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
    web_response, error = page_request(url)
    if error:
        return None, error
    if web_response is None:
        return None, "Resposta da página foi nula (sem erro explícito de request)."
    return BeautifulSoup(web_response.content, parser), None

# --- Funções para ConcursosNoBrasil.com ---
def get_target_url_and_validate_category_cnb(category: str):
    if not isinstance(category, str) or not ((len(category) == 2 and category.isalpha()) or category.lower() == 'br'):
        error_message = "Categoria para ConcursosNoBrasil inválida. Deve ser uma sigla de estado (2 letras) ou 'br' para Nacional."
        return None, error_message
    cat_lower = category.lower()
    if cat_lower != 'br' and cat_lower not in AVAILABLE_CATEGORIES_CNB:
        error_message = f"Sigla de estado '{category}' inválida para ConcursosNoBrasil."
        return None, error_message
    return BASE_URL_CNB + cat_lower, None

def get_category_item_status_cnb(item_row) -> str:
    primeiro_td = item_row.find('td')
    if primeiro_td and primeiro_td.find('div', class_='label-previsto'):
        return 'previsto'
    return 'aberto'

def parse_workplaces_common(workplaces_text: str): # Tornada comum
    cleaned_text = workplaces_text.strip().lower()
    if not cleaned_text or cleaned_text == "não informado" or cleaned_text == "ver detalhes":
        return "Ver detalhes" # Padronizado
    if cleaned_text == "várias":
        return "Várias"

    if cleaned_text.isdigit():
        return int(cleaned_text)
    
    # Tenta extrair números de strings como "150 vagas", "CR + 10", "1.230"
    numeric_part = "".join(filter(lambda char: char.isdigit() or char == '.', cleaned_text))
    numeric_part = numeric_part.replace('.', '') # Remove pontos de milhar para conversão
    if numeric_part.isdigit():
        try:
            num = int(numeric_part)
            if num > 0 : return num # Retorna apenas se for um número plausível de vagas
        except ValueError:
            pass
            
    return workplaces_text.strip() # Retorna texto original se não for puramente numérico ou "Várias"

def extract_concursos_data_cnb(soup: BeautifulSoup):
    concursos_disponiveis = []
    main_content = soup.find('main', id='conteudo', class_='taxonomy')
    if not main_content:
        return None, "Não foi possível encontrar a seção de conteúdo principal ('main#conteudo.taxonomy') no site ConcursosNoBrasil."
    tabela_concursos = main_content.find('table')
    if not tabela_concursos:
        return None, "Não foi possível encontrar a tabela de concursos dentro do conteúdo principal do site ConcursosNoBrasil."
    tabela_corpo = tabela_concursos.find('tbody')
    if not tabela_corpo:
        return None, "Não foi possível encontrar o corpo da tabela de concursos ('tbody') na página do ConcursosNoBrasil."
    itens_disponiveis_na_categoria = tabela_corpo.find_all('tr')
    if not itens_disponiveis_na_categoria:
        return [], "Nenhum concurso encontrado na tabela para esta categoria no site ConcursosNoBrasil."

    for item_row in itens_disponiveis_na_categoria:
        tds = item_row.find_all('td')
        if not tds or len(tds) < 2: continue
        link_tag = tds[0].find('a')
        organizacao, link_concurso = "Não informado", "#"
        if link_tag:
            organizacao = link_tag.text.strip() if link_tag.text else "Não informado"
            raw_link = link_tag.get('href')
            if raw_link:
                link_concurso = SITE_DOMAIN_CNB + raw_link if raw_link.startswith('/') else raw_link
        vagas_disponiveis_raw = tds[1].text.strip() if tds[1] and tds[1].text else "Não informado"
        vagas_disponiveis_parsed = parse_workplaces_common(vagas_disponiveis_raw)
        status_concurso = get_category_item_status_cnb(item_row)
        concursos_disponiveis.append({
            'organizacao': organizacao,
            'vagasDisponiveis': vagas_disponiveis_parsed,
            'link': link_concurso,
            'status': status_concurso
        })
    return concursos_disponiveis, None

# --- Funções para PCIConcursos.com.br (Notícias da Capa) ---
def extract_status_pci(section_tag):
    h3_tag = section_tag.find('h3')
    if h3_tag:
        # Status como <span style="font-size:0.65rem;" class="badge-outline badge-outline-success">prorrogado</span>
        # geralmente é irmão do <h3> ou dentro dele, ou logo após
        badge = h3_tag.find_next_sibling('span', class_=lambda x: x and 'badge-outline' in x)
        if badge and badge.text:
            return badge.text.strip().lower()
        # Pode estar dentro do próprio link do h3 também
        badge_in_link = h3_tag.find('span', class_=lambda x: x and 'badge-outline' in x)
        if badge_in_link and badge_in_link.text:
            return badge_in_link.text.strip().lower()
    return "aberto" # Default

def extract_vagas_pci(text_content: str, title_content: str):
    if not text_content and not title_content:
        return "Ver detalhes"

    # Tenta encontrar "XXX vagas" no texto ou título
    for text_to_search in [title_content, text_content]:
        if not text_to_search: continue
        # Regex para encontrar números (incluindo com ponto) seguidos de "vaga(s)"
        match = re.search(r'(\d{1,3}(?:\.\d{3})*|\d+)\s+vagas', text_to_search, re.IGNORECASE)
        if match:
            vagas_str = match.group(1).replace('.', '') # Remove pontos de milhar
            if vagas_str.isdigit():
                return int(vagas_str)
        # Caso de "uma vaga"
        if "uma vaga" in text_to_search.lower():
            return 1
            
    if title_content and "vagas" in title_content.lower(): # Se a palavra "vagas" está no título mas não achou número
        return "Várias"
    if text_content and "vagas" in text_content.lower(): # Se a palavra "vagas" está no texto mas não achou número
        return "Várias"
        
    return "Ver detalhes"

def extract_concursos_data_pci(soup: BeautifulSoup):
    concursos_pci = []
    noticias_capa_div = soup.find('div', id='noticias_capa')
    if not noticias_capa_div:
        return None, "Não foi possível encontrar a seção de notícias ('div#noticias_capa') no PCI Concursos."

    noticias = noticias_capa_div.find_all('section', class_='noticia')
    if not noticias:
        return [], "Nenhuma notícia de concurso encontrada na capa do PCI Concursos." # Retorna lista vazia e msg

    for noticia_section in noticias:
        h3_tag = noticia_section.find('h3')
        if not h3_tag: continue
        
        link_tag = h3_tag.find('a')
        if not link_tag or not link_tag.get('href'): continue

        titulo_concurso = link_tag.get_text(strip=True)
        link_detalhes = link_tag['href']
        # Garante que o link é absoluto
        if not link_detalhes.startswith('http'):
            link_detalhes = SITE_DOMAIN_PCI + link_detalhes if link_detalhes.startswith('/') else SITE_DOMAIN_PCI + "/" + link_detalhes
        
        primeiro_p_tag = noticia_section.find('p')
        resumo = primeiro_p_tag.get_text(strip=True) if primeiro_p_tag else "Ver detalhes no link."
        
        vagas = extract_vagas_pci(resumo, titulo_concurso)
        status_pci = extract_status_pci(noticia_section)

        concursos_pci.append({
            'organizacao': titulo_concurso,
            'link': link_detalhes,
            'vagasDisponiveis': vagas,
            'resumo': resumo,
            'status': status_pci,
            'estado_inferido': "N/A", # Não dá para inferir da capa com segurança
            'regiao_inferida': "N/A"  # Não dá para inferir da capa com segurança
        })
    return concursos_pci, None