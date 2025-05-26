# generator/scraper_leis_planalto.py
import requests
from bs4 import BeautifulSoup, Comment
from urllib.parse import urljoin, urlparse
import time
import logging
import re
from datetime import datetime

from django.utils import timezone
from django.conf import settings
from django.db import transaction # Para transações atômicas

# Importe os modelos Django.
MODELS_AVAILABLE = False
try:
    from .models import LeiPlanalto, TipoNormaPlanalto
    if LeiPlanalto and TipoNormaPlanalto:
        logging.info("MODELS_LOAD_SUCCESS_SCRAPER: Modelos LeiPlanalto e TipoNormaPlanalto importados com SUCESSO.")
        MODELS_AVAILABLE = True
    else:
        logging.error("MODELS_LOAD_ISSUE_SCRAPER: Modelos LeiPlanalto ou TipoNormaPlanalto são None APÓS o import.")
except ImportError as e:
    logging.basicConfig(level=logging.ERROR)
    logging.error(f"CRITICAL_MODEL_IMPORT_ERROR_SCRAPER: {e}. Verifique 'generator/models.py' e migrações.")

logger = logging.getLogger(__name__)

class PlanaltoLeisScraper:
    BASE_URL = "https://www.planalto.gov.br/ccivil_03/"
    DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; GemmaLeisScraperBot/1.5; +[seu_contato_ou_link_do_projeto])"

    def __init__(self, max_depth=2, start_url=None, **kwargs):
        self.max_depth = int(max_depth)
        self.start_url = start_url if start_url else self.BASE_URL
        self.visited_urls_session = set()
        # Contadores para a sessão de scraping
        self.created_count_session = 0
        self.updated_count_session = 0
        self.error_count_session = 0

        scraper_config = getattr(settings, 'SCRAPER_CONFIG_PLANALTO', {})
        self.user_agent = scraper_config.get('USER_AGENT', self.DEFAULT_USER_AGENT)
        self.request_timeout = scraper_config.get('REQUEST_TIMEOUT', 30)
        self.delay_between_requests = scraper_config.get('DELAY_BETWEEN_REQUESTS', 2.8)
        self.max_links_per_page = scraper_config.get('MAX_LINKS_PER_PAGE_PLANALTO', 50)

        logger.info(
            f"PlanaltoLeisScraper (Salvamento Dinâmico) INICIALIZADO: max_depth={self.max_depth}, "
            f"start_url='{self.start_url}', delay={self.delay_between_requests}s, "
            f"timeout={self.request_timeout}s"
        )

    def _make_request(self, url):
        # ... (método _make_request como na versão anterior, com logging) ...
        logger.debug(f"REQUEST: Fazendo requisição para: {url}")
        try:
            headers = {'User-Agent': self.user_agent}
            response = requests.get(url, headers=headers, timeout=self.request_timeout, allow_redirects=True)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', '').lower()
            if 'html' not in content_type:
                logger.warning(f"REQUEST_CONTENT_TYPE_WARNING: Conteúdo não é HTML em {url}. Content-Type: {content_type}. Ignorando.")
                return None, f"Conteúdo não HTML: {content_type}"
            
            detected_encoding = response.encoding if response.encoding else response.apparent_encoding
            logger.debug(f"REQUEST_ENCODING: Encoding detectado/usado para {url}: {detected_encoding}")
            soup = BeautifulSoup(response.content, 'html.parser', from_encoding=detected_encoding)
            
            logger.debug(f"REQUEST_DELAY: Aguardando {self.delay_between_requests}s após requisição para {url}")
            time.sleep(self.delay_between_requests)
            return soup, None
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"REQUEST_HTTP_ERROR: Erro HTTP {http_err.response.status_code} ao acessar {url}: {http_err}")
            return None, str(http_err)
        except requests.exceptions.RequestException as req_err:
            logger.error(f"REQUEST_GENERAL_ERROR: Erro na requisição para {url}: {req_err}")
            return None, str(req_err)
        except Exception as e:
            logger.error(f"REQUEST_UNEXPECTED_ERROR: Erro inesperado durante a requisição para {url}: {e}", exc_info=True)
            return None, str(e)

    def _normalize_url(self, url, base_for_join=None):
        # ... (método _normalize_url como na versão anterior) ...
        try:
            if base_for_join:
                abs_url = urljoin(base_for_join, url.strip())
            else:
                abs_url = url.strip()
            
            parsed = urlparse(abs_url)
            url_sem_fragmento = parsed.scheme + "://" + parsed.netloc + parsed.path
            if parsed.query:
                 url_sem_fragmento += "?" + parsed.query
            return url_sem_fragmento
        except Exception as e:
            logger.warning(f"URL_NORMALIZE_ERROR: Não foi possível normalizar a URL '{url}'. Erro: {e}")
            return None

    def _is_law_page(self, url, soup):
        # ... (lógica de _is_law_page como na versão anterior, com seus refinamentos) ...
        # É crucial que esta função seja precisa.
        if not soup: return False
        path = urlparse(url).path.lower() # url já deve estar normalizada aqui
        if not path.endswith(('.htm', '.html')): return False
        if path == "/" or path == "/ccivil_03/" or path == "/ccivil_03/index.htm": return False

        law_path_keywords = ['/lei/', '/decreto/', '/leis/', '/decretos/', '/lcp/', '/mpv/', '/dsn/', '/ato', '/emc/', '/constituicao/']
        is_potential_law_path = any(kw in path for kw in law_path_keywords) or \
                                re.search(r'/leis/l\d+\.htm', path) or \
                                re.search(r'/decreto/d\d+\.htm', path)
        if not is_potential_law_path:
            return False
        
        excluded_path_keywords = ['indice', 'index', 'sumario', 'relacao', 'quadro', 'revogado', 'plano', 'mensagem_veto/anterior', 'decretos/quadros/']
        if any(kw_ignorar in path for kw_ignorar in excluded_path_keywords):
            return False

        title_text = ""
        if soup.title and soup.title.string: # Proteção contra soup.title ser None
            title_text = soup.title.string.strip().lower()
        
        excluded_title_keywords = ['índice de', 'sumário de', 'relação de', 'lista de', 'legislação federal', 'atos do poder legislativo', 'planalto']
        if any(index_kw in title_text for index_kw in excluded_title_keywords) and len(title_text) < 60 : # Aumentei o len para pegar títulos mais genéricos
             return False
        
        texto_impressao = soup.find(id="textoimpressao")
        if texto_impressao:
            return True
        
        # Heurística adicional para conteúdo
        body_text_length = len(soup.body.get_text(strip=True)) if soup.body else 0
        if body_text_length > 1000:
             # Verifica se não é uma lista longa de links (comum em índices)
            num_links_no_corpo = len(soup.body.find_all('a', href=True)) if soup.body else 0
            if num_links_no_corpo < 50 : # Páginas de lei geralmente têm menos links de navegação interna
                return True
        
        return False

    def _extract_law_data(self, url_original_com_fragmento, soup):
        if not soup: return None
        
        url_normalizada_para_db = self._normalize_url(url_original_com_fragmento)
        if not url_normalizada_para_db:
             logger.warning(f"EXTRACT_DATA_URL_NORM_FAIL: {url_original_com_fragmento}")
             return None

        data = {"url_original": url_normalizada_para_db}
        logger.info(f"EXTRACT_DATA: Extraindo de: {url_normalizada_para_db} (Original: {url_original_com_fragmento})")

        # Título / Ementa
        title_tag = soup.find('title')
        page_title = title_tag.string.strip().replace("\n", " ").replace("\r", " ") if title_tag and title_tag.string else ""
        
        ementa_text = ""
        # Tenta encontrar <p align="CENTER"> com texto descritivo para ementa
        # Tenta também <p class="ementa"> ou <div class="ementa">
        possible_ementa_tags = soup.find_all(['p', 'div'], attrs={'align': 'CENTER', 'class': re.compile(r'ementa', re.I)}, limit=5)
        if not possible_ementa_tags: # Fallback se não achar com classe ementa
            possible_ementa_tags = soup.find_all('p', align='CENTER', limit=10)


        for p_tag in possible_ementa_tags:
            current_p_text = " ".join(s.strip() for s in p_tag.find_all(string=True, recursive=True) if s.strip())
            if len(current_p_text) > 70 and any(kw.lower() in current_p_text.lower() for kw in ['dispõe sobre', 'altera', 'institui', 'regulamenta', 'cria', 'autoriza', 'define', 'estabelece']):
                ementa_text = current_p_text
                break
        
        if ementa_text:
            data['titulo_ou_ementa'] = ementa_text
        elif page_title:
            data['titulo_ou_ementa'] = page_title
        else:
            data['titulo_ou_ementa'] = f"Título/Ementa não disponível para {url_normalizada_para_db}"

        # Tipo, Número, Ano, Data
        norma_id_str = None
        header_ps = soup.find_all('p', align='CENTER', limit=10) 
        for p_tag in header_ps:
            text_content = " ".join(s.strip() for s in p_tag.find_all(string=True, recursive=True) if s.strip())
            if not text_content: continue
            text_upper = text_content.upper()

            # Não pegar a ementa como string de identificação da norma
            if len(text_upper) > 150 or any(ementa_kw.upper() in text_upper for ementa_kw in ['DISPÕE SOBRE', 'ALTERA A LEI', 'INSTITUI']):
                continue

            if any(tipo_kw in text_upper for tipo_kw in ['LEI Nº', 'DECRETO Nº', 'LEI COMPLEMENTAR Nº', 'MEDIDA PROVISÓRIA Nº', 'DECRETO-LEI Nº', 'EMENDA CONSTITUCIONAL Nº', 'PORTARIA Nº']):
                norma_id_str = text_content # Usa o texto original para preservar case se necessário
                break
        
        if norma_id_str:
            logger.debug(f"EXTRACT_DATA_ID_STR: String de ID: '{norma_id_str}'")
            # Regex aprimorado
            pattern = re.compile(
                r"^\s*(LEI\s+COMPLEMENTAR|LEI|DECRETO-LEI|DECRETO|MEDIDA\s+PROVISÓRIA|EMENDA\s+CONSTITUCIONAL|PORTARIA|RESOLUÇÃO)\s*"
                r"(?:Nº|N\.?|N\s)?\s*"
                r"([\d\.\/,-]+(?:-?\w{1,3})?)\s*,?\s*" # Número
                r"(?:DE\s*)?"
                r"(\d{1,2}(?:º)?\s+DE\s+[\wÇÃÕÉÁÍÓÚ]+\s+DE\s+\d{4})", # Data
                re.IGNORECASE
            )
            match = pattern.match(norma_id_str)
            if match:
                data['tipo_norma_str'] = match.group(1).strip().title()
                data['numero_norma'] = match.group(2).strip()
                data['data_publicacao_str'] = match.group(3).strip()
            else: # Tenta sem a data no mesmo padrão
                pattern_no_date = re.compile(
                     r"^\s*(LEI\s+COMPLEMENTAR|LEI|DECRETO-LEI|DECRETO|MEDIDA\s+PROVISÓRIA|EMENDA\s+CONSTITUCIONAL|PORTARIA|RESOLUÇÃO)\s*"
                     r"(?:Nº|N\.?|N\s)?\s*"
                     r"([\d\.\/,-]+(?:-?\w{1,3})?)",
                     re.IGNORECASE
                )
                match_no_date = pattern_no_date.match(norma_id_str)
                if match_no_date:
                    data['tipo_norma_str'] = match_no_date.group(1).strip().title()
                    data['numero_norma'] = match_no_date.group(2).strip()
                # Tenta pegar a data de outra parte da string de ID se não veio junto
                if not data.get('data_publicacao_str'):
                    match_data_isolada = re.search(r"(\d{1,2}(?:º)?\s+DE\s+[\wÇÃÕÉÁÍÓÚ]+\s+DE\s+\d{4})", norma_id_str, re.IGNORECASE)
                    if match_data_isolada:
                        data['data_publicacao_str'] = match_data_isolada.group(1).strip()
        else:
            logger.warning(f"EXTRACT_DATA_ID_STR_FAIL: Sem string de ID para {url_normalizada_para_db}")
        
        # Processar data_publicacao e ano_norma
        if data.get('data_publicacao_str'):
            data_str_raw = data['data_publicacao_str']
            data_str_norm = re.sub(r'(\d+)º', r'\1', data_str_raw) # Remove 'º'
            meses_pt = {'JANEIRO': '01', 'FEVEREIRO': '02', 'MARÇO': '03', 'ABRIL': '04', 'MAIO': '05', 'JUNHO': '06', 'JULHO': '07', 'AGOSTO': '08', 'SETEMBRO': '09', 'OUTUBRO': '10', 'NOVEMBRO': '11', 'DEZEMBRO': '12'}
            for nome_mes, num_mes in meses_pt.items():
                data_str_norm = data_str_norm.upper().replace(nome_mes, num_mes)
            
            parsed_date = None
            # Tenta "DD DE MM DE YYYY" e "DD/MM/YYYY" e "DD.MM.YYYY"
            date_try_formats = ["%d DE %m DE %Y", "%d/%m/%Y", "%d.%m.%Y"]
            for fmt_idx, fmt_str_original in enumerate(date_try_formats):
                # Normaliza para / antes de tentar o formato com /
                current_date_str_to_try = data_str_norm.replace(" DE ", "/").replace(".", "/") if "/" in fmt_str_original else data_str_norm
                try:
                    # logger.debug(f"Tentando formato de data '{fmt_str_original}' com string '{current_date_str_to_try}'")
                    parsed_date = datetime.strptime(current_date_str_to_try, fmt_str_original).date()
                    break 
                except ValueError:
                    # logger.debug(f"Formato de data '{fmt_str_original}' falhou para '{current_date_str_to_try}'")
                    continue
            
            if parsed_date:
                data['data_publicacao'] = parsed_date
                data['ano_norma'] = parsed_date.year
            else:
                logger.warning(f"EXTRACT_DATA_DATE_FAIL: Não parseou data: '{data['data_publicacao_str']}' de {url_normalizada_para_db}")
                data['data_publicacao'] = None
        
        if not data.get('ano_norma') and data.get('numero_norma'):
            match_ano_num = re.search(r'[\/\-\.\s](\d{4})$', data['numero_norma']) # Procura por 4 dígitos no final após separador
            if not match_ano_num:
                 match_ano_num = re.search(r'[\/\-\.\s](\d{2})$', data['numero_norma']) # Tenta 2 dígitos
            
            if match_ano_num:
                ano_str_num = match_ano_num.group(1)
                try:
                    if len(ano_str_num) == 2:
                        ano_int = int(ano_str_num)
                        current_year_last_two_digits = int(str(datetime.now().year)[2:])
                        data['ano_norma'] = 1900 + ano_int if ano_int > current_year_last_two_digits + 10 else 2000 + ano_int # Heurística para anos de 2 dígitos
                    elif len(ano_str_num) == 4:
                        data['ano_norma'] = int(ano_str_num)
                except ValueError:
                    logger.warning(f"EXTRACT_DATA_YEAR_FAIL: Erro ao converter ano '{ano_str_num}' de {data['numero_norma']}")

        # Texto Integral HTML
        texto_container = soup.find(id="textoimpressao")
        if texto_container:
            temp_soup_container = BeautifulSoup(str(texto_container), 'html.parser')
            for s in temp_soup_container(['script', 'style', 'form', 'iframe', 'button', 'input', 'select', 'textarea', 'img', 'noscript', 'table']): s.decompose() # Adicionado table
            for comment in temp_soup_container.find_all(string=lambda text: isinstance(text, Comment)): comment.extract()
            data['texto_integral_html'] = temp_soup_container.prettify()
        else:
            logger.warning(f"EXTRACT_DATA_NO_TEXTOIMPRESSAO: #textoimpressao não encontrado em {url_normalizada_para_db}. Usando body.")
            if soup.body:
                # Tenta limpar um pouco mais o body
                body_copy = BeautifulSoup(str(soup.body), 'html.parser')
                for s in body_copy(['script', 'style', 'form', 'iframe', 'button', 'input', 'select', 'textarea', 'img', 'noscript', 'header', 'footer', 'nav', '.noprint', '#rodape', '#cabecalho', 'link', 'meta']): s.decompose()
                for tag_to_unwrap in body_copy.find_all(['font', 'span']): # Tira tags de formatação desnecessárias
                    tag_to_unwrap.unwrap()
                # Remove tabelas de navegação no topo/rodapé
                for table in body_copy.find_all('table'):
                    if len(table.find_all('a')) > 5 and len(table.get_text(strip=True)) < 300 : # Heurística para tabela de navegação
                        table.decompose()
                        logger.debug(f"Removida tabela de navegação potencial de {url_normalizada_para_db}")

                data['texto_integral_html'] = body_copy.prettify()
            else:
                data['texto_integral_html'] = None
                logger.error(f"EXTRACT_DATA_NO_BODY: Corpo da página não encontrado em {url_normalizada_para_db}")

        # Fallbacks e limpeza final
        if not data.get('tipo_norma_str'): data['tipo_norma_str'] = "Norma Não Especificada"
        data['numero_norma'] = data.get('numero_norma', "S/N").replace(".","") # Remove pontos de milhar do número
        if not data.get('titulo_ou_ementa'): data['titulo_ou_ementa'] = f"Documento de {url_normalizada_para_db}"


        logger.debug(f"EXTRACT_DATA_RESULT: Para {url_normalizada_para_db}: Tipo='{data.get('tipo_norma_str')}', Num='{data.get('numero_norma')}', Ano='{data.get('ano_norma')}', Data='{data.get('data_publicacao')}', Título='{str(data.get('titulo_ou_ementa'))[:30]}...'")
        return data

    def _get_relevant_links_from_page(self, base_url_page, soup):
        # ... (lógica de _get_relevant_links_from_page como na versão anterior) ...
        links = set()
        if not soup: return list(links)
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            if not href or href.startswith(('#', 'javascript:', 'mailto:')): continue
            
            normalized_link = self._normalize_url(href, base_url_page)
            if not normalized_link: continue

            parsed_full_url = urlparse(normalized_link)
            parsed_base_url = urlparse(self.BASE_URL)

            if not parsed_full_url.netloc.endswith('planalto.gov.br'): continue
            # Permite links para /ccivil_03 e também para a raiz do ccivil (ex: /ccivil_03/decreto/Quadrante_decretos.htm)
            if not (parsed_full_url.path.startswith('/ccivil_03/') or parsed_full_url.path.startswith('/ccivil/')):
                continue
            if '.' in parsed_full_url.path.split('/')[-1] and not parsed_full_url.path.lower().endswith(('.htm', '.html')):
                continue
            
            link_text_lower = a_tag.get_text().lower().strip()
            excluded_link_texts = [
                'página inicial', 'voltar', 'imprimir', 'planalto', 'casa civil',
                'secretaria-geral', 'gsi', 'estado', 'governo', 'legislação',
                'fale conosco', 'mapa do site', 'acesso à informação'
            ]
            if any(stop_text in link_text_lower for stop_text in excluded_link_texts) and len(link_text_lower) < 30 :
                continue
            
            if normalized_link == base_url_page: continue # Evita link para a própria página

            links.add(normalized_link)
        
        # logger.debug(f"GET_LINKS_FOUND: {len(links)} links relevantes encontrados em {base_url_page}.")
        return list(links)

    def _save_single_law_to_db(self, law_data):
        """Salva uma única lei no banco de dados."""
        if not MODELS_AVAILABLE:
            logger.error(f"SAVE_SINGLE_LAW_FAIL_MODELS: Modelos não disponíveis. Não salvando: {law_data.get('url_original')}")
            self.error_count_session += 1
            return False

        url_original_db = str(law_data.get('url_original', '')).strip()
        if not url_original_db:
            logger.warning(f"SAVE_SINGLE_LAW_NO_URL: Dados da lei sem URL original. Título: {str(law_data.get('titulo_ou_ementa'))[:100]}. Ignorando.")
            self.error_count_session += 1
            return False

        logger.debug(f"SAVE_SINGLE_LAW_PROCESSING: URL='{url_original_db}', Título='{str(law_data.get('titulo_ou_ementa'))[:50]}'")
        try:
            with transaction.atomic():
                tipo_norma_str = str(law_data.get("tipo_norma_str", "Norma Não Especificada")).strip()[:100]
                if not tipo_norma_str: tipo_norma_str = "Norma Não Especificada"
                tipo_norma_obj, tipo_created = TipoNormaPlanalto.objects.get_or_create(nome=tipo_norma_str)
                if tipo_created: logger.info(f"SAVE_SINGLE_LAW_TIPONORMA_CREATED: '{tipo_norma_str}'")

                defaults = {
                    'titulo_ou_ementa': law_data.get('titulo_ou_ementa'),
                    'numero_norma': str(law_data.get('numero_norma', '')).strip()[:100] or None,
                    'ano_norma': int(law_data.get('ano_norma')) if str(law_data.get('ano_norma','')).strip().isdigit() else None,
                    'tipo_norma': tipo_norma_obj,
                    'data_publicacao': law_data.get('data_publicacao'),
                    'texto_integral_html': law_data.get('texto_integral_html'),
                    'ultima_verificacao_coleta': timezone.now()
                }
                defaults_cleaned = {k: v for k, v in defaults.items() if v is not None or k in ['texto_integral_html', 'titulo_ou_ementa', 'numero_norma', 'ano_norma']}
                
                if defaults_cleaned.get('titulo_ou_ementa') is None and not LeiPlanalto._meta.get_field('titulo_ou_ementa').blank:
                    defaults_cleaned['titulo_ou_ementa'] = "Título/Ementa Indisponível"
                if defaults_cleaned.get('texto_integral_html') is None and not LeiPlanalto._meta.get_field('texto_integral_html').blank:
                     defaults_cleaned['texto_integral_html'] = "" # Campo TextField pode ser string vazia se blank=True

                # logger.debug(f"SAVE_SINGLE_LAW_DEFAULTS for {url_original_db}: { {k: (str(v)[:70] + '...' if isinstance(v, str) and len(v) > 70 else v) for k,v in defaults_cleaned.items()} }")

                obj, created = LeiPlanalto.objects.update_or_create(
                    url_original=url_original_db,
                    defaults=defaults_cleaned
                )
                if created:
                    self.created_count_session += 1
                    logger.info(f"SAVE_SINGLE_LAW_CREATED: ID={obj.id}, URL='{obj.url_original}'")
                else:
                    self.updated_count_session += 1
                    logger.info(f"SAVE_SINGLE_LAW_UPDATED: ID={obj.id}, URL='{obj.url_original}'")
                return True
        except Exception as e:
            self.error_count_session += 1
            logger.error(f"SAVE_SINGLE_LAW_ERROR: Erro ao salvar lei URL {url_original_db}: {e}", exc_info=True)
            return False


    def scrape_recursively(self, current_url, depth):
        current_url_normalized = self._normalize_url(current_url)
        if not current_url_normalized:
            logger.warning(f"SCRAPE_INVALID_URL: '{current_url}', pulando.")
            return

        if depth > self.max_depth:
            return
        if current_url_normalized in self.visited_urls_session:
            logger.debug(f"SCRAPE_VISITED: URL já visitada: {current_url_normalized}")
            return

        logger.info(f"SCRAPE_VISITING: Nível {depth}/{self.max_depth}: {current_url_normalized}")
        self.visited_urls_session.add(current_url_normalized)

        soup, error_msg = self._make_request(current_url_normalized)
        if error_msg or not soup:
            logger.warning(f"SCRAPE_FETCH_FAIL: {current_url_normalized}. Erro: {error_msg}")
            return

        if self._is_law_page(current_url_normalized, soup):
            law_data = self._extract_law_data(current_url, soup) # Passa a URL original para _extract_law_data
            if law_data and law_data.get('url_original') and \
               (law_data.get('titulo_ou_ementa') or law_data.get('numero_norma')):
                logger.info(f"  +++ LAW_DATA_EXTRACTED: {law_data['url_original']} - Tentando salvar dinamicamente...")
                self._save_single_law_to_db(law_data) # <<--- SALVAMENTO IMEDIATO
            else:
                logger.warning(f"  LAW_DATA_INSUFFICIENT: Dados insuficientes em {current_url_normalized}.")
        
        if depth < self.max_depth:
            links_to_follow = self._get_relevant_links_from_page(current_url_normalized, soup)
            if not links_to_follow:
                return
            # logger.info(f"  SCRAPE_FOLLOWING: {len(links_to_follow)} links em {current_url_normalized} para Nível {depth + 1}.")
            
            for i, link in enumerate(links_to_follow):
                if i >= self.max_links_per_page and self.max_links_per_page > 0 :
                    logger.info(f"  SCRAPE_LINK_LIMIT: Limite de links por página atingido para {current_url_normalized}.")
                    break
                self.scrape_recursively(link, depth + 1)

    def run(self):
        logger.info(f"RUN_START: INICIANDO ScraperLeisPlanalto (Salv. Dinâmico): max_depth={self.max_depth}, start_url='{self.start_url}'")
        self.visited_urls_session.clear()
        self.created_count_session = 0 # Reseta contadores da sessão
        self.updated_count_session = 0
        self.error_count_session = 0
        
        self.scrape_recursively(self.start_url, 0)
        
        logger.info(f"RUN_END: FINALIZADO ScraperLeisPlanalto. "
                    f"Criadas={self.created_count_session}, Atualizadas={self.updated_count_session}, Erros={self.error_count}. "
                    f"Total de URLs visitadas: {len(self.visited_urls_session)}")

def run_planalto_leis_scraper_main(max_depth=1, start_url=None):
    logger.info(f"WRAPPER_CALL: run_planalto_leis_scraper_main (Salv. Dinâmico) com max_depth={max_depth}, start_url={start_url or 'PADRÃO'}")
    if not MODELS_AVAILABLE:
        logger.critical("WRAPPER_MODELS_UNAVAILABLE: Modelos Django não carregados. Abortando scraper de leis.")
        return

    scraper = PlanaltoLeisScraper(max_depth=max_depth, start_url=start_url)
    scraper.run()