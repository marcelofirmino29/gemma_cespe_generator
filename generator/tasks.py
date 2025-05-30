# generator/tasks.py
from celery import shared_task, states
from celery.exceptions import Ignore
from django.conf import settings
import logging
import time

from generator.scraper_leis_planalto import run_planalto_leis_scraper_main

# --- Scraper de Leis do Planalto ---
try:
    from .scraper_leis_planalto import run_planalto_leis_scraper_main # Função principal do scraper de leis
except ImportError as e:
    logging.error(f"Erro ao importar 'run_planalto_leis_scraper_main' de '.scraper_leis_planalto': {e}")
    run_planalto_leis_scraper_main = None

# --- Scraper de Provas PCI Concursos ---
try:
    # Presumindo que seu scraper PCI está em scraper_provas_pci.py
    # e tem a função scraper_pci_provas_principal adaptada
    from .scraper_provas_pci import scraper_pci_provas_principal
except ImportError as e:
    logging.error(f"Erro ao importar 'scraper_pci_provas_principal' de '.scraper_provas_pci': {e}")
    scraper_pci_provas_principal = None


logger = logging.getLogger(__name__)


# --- TAREFA PARA O SCRAPER DE LEIS DO PLANALTO ---
@shared_task(name="generator.tasks.scrape_planalto_laws_task", bind=True, max_retries=2, default_retry_delay=10*60) # Ex: Tenta 2 vezes, delay de 10 min
def scrape_planalto_laws_task(self, **kwargs_from_beat_or_manual_call):
    task_id = self.request.id
    logger.info(f"[TASK_ID:{task_id}] Iniciando tarefa Celery scrape_planalto_laws_task com args: {kwargs_from_beat_or_manual_call}")

    if run_planalto_leis_scraper_main is None:
        logger.error(f"[TASK_ID:{task_id}] A função do scraper de Leis do Planalto não pôde ser importada. A tarefa não pode ser executada.")
        self.update_state(state=states.FAILURE, meta={'exc_type': 'ImportError', 'exc_message': 'Função do scraper de Leis do Planalto não encontrada.'})
        raise Ignore() # Ignora a tarefa para não tentar novamente se a importação falhou

    # Parâmetros para o scraper de leis, com defaults
    default_planalto_config = getattr(settings, 'SCRAPER_CONFIG_PLANALTO', {})
    params_para_funcao_planalto = {
        'max_depth': kwargs_from_beat_or_manual_call.get(
            'max_depth', default_planalto_config.get('MAX_DEPTH', 6) # Comece com profundidade baixa para teste
        ),
        'start_url': kwargs_from_beat_or_manual_call.get(
            'start_url', default_planalto_config.get('START_URL', None) # Se None, o scraper usa sua URL base
        ),
        # Adicione outros parâmetros que run_planalto_leis_scraper_main possa aceitar
    }
    # Não é necessário params_para_funcao_limpos se a função do scraper já lida com None como default

    logger.info(f"[TASK_ID:{task_id}] Parâmetros para a função do Scraper de Leis: {params_para_funcao_planalto}")

    try:
        time.sleep(3) # Pequena pausa
        # Chame a FUNÇÃO principal do seu scraper de leis
        # Assumindo que run_planalto_leis_scraper_main lida com salvamento no BD e logging interno
        run_planalto_leis_scraper_main(**params_para_funcao_planalto)

        success_message = f"[TASK_ID:{task_id}] Tarefa Celery scrape_planalto_laws_task concluída."
        # A função run_planalto_leis_scraper_main pode não retornar dados contáveis,
        # então o log de sucesso é mais genérico aqui.
        logger.info(success_message)
        return success_message
    except Exception as exc:
        logger.error(f"[TASK_ID:{task_id}] Erro na tarefa Celery scrape_planalto_laws_task: {exc}", exc_info=True)
        raise self.retry(exc=exc) # Usa a configuração de retentativa do decorator


# --- TAREFA PARA O SCRAPER DE PROVAS PCI CONCURSOS ---
@shared_task(bind=True, name="generator.tasks.run_pci_scraper_task", max_retries=3, default_retry_delay=5*60)
def run_pci_scraper_task(self, **kwargs_from_beat_or_manual_call):
    task_id = self.request.id
    logger.info(f"[TASK_ID:{task_id}] Iniciando tarefa Celery run_pci_scraper_task com args: {kwargs_from_beat_or_manual_call}")

    if scraper_pci_provas_principal is None:
        logger.error(f"[TASK_ID:{task_id}] A função do scraper PCI não pôde ser importada. A tarefa não pode ser executada.")
        self.update_state(state=states.FAILURE, meta={'exc_type': 'ImportError', 'exc_message': 'Função do scraper PCI não encontrada.'})
        raise Ignore()

    default_scraper_config = getattr(settings, 'SCRAPER_CONFIG_PCICONCURSOS', {})
    params_para_funcao = {
        'max_categorias_cargo': kwargs_from_beat_or_manual_call.get(
            'max_categorias_cargo', default_scraper_config.get('MAX_CATEGORIAS_CARGO', 3)
        ),
        'max_paginas_por_categoria': kwargs_from_beat_or_manual_call.get(
            'max_paginas_por_categoria', default_scraper_config.get('MAX_PAGINAS_POR_CATEGORIA', 1)
        ),
        'ano_alvo': kwargs_from_beat_or_manual_call.get(
            'ano_alvo', default_scraper_config.get('ANO_ALVO', None)
        ),
        'max_profundidade_recursao': kwargs_from_beat_or_manual_call.get(
            'max_profundidade_recursao', default_scraper_config.get('MAX_PROFUNDIDADE_RECURSAO', 1)
        ),
    }
    params_para_funcao_limpos = {k: v for k, v in params_para_funcao.items() if v is not None}
    logger.info(f"[TASK_ID:{task_id}] Parâmetros para a função do Scraper PCI: {params_para_funcao_limpos}")

    try:
        time.sleep(2) # Pequena pausa antes de iniciar
        dados_coletados = scraper_pci_provas_principal(**params_para_funcao_limpos)
        success_message = f"[TASK_ID:{task_id}] Tarefa Celery run_pci_scraper_task concluída."
        if hasattr(dados_coletados, '__len__'): # Verifica se dados_coletados é uma coleção com tamanho
            logger.info(f"{success_message} {len(dados_coletados)} itens processados.")
        else:
            logger.info(f"{success_message} Função do scraper não retornou uma coleção de dados contável ou nenhum item processado.")
        return success_message
    except Exception as exc:
        logger.error(f"[TASK_ID:{task_id}] Erro na tarefa Celery run_pci_scraper_task: {exc}", exc_info=True)
        raise self.retry(exc=exc) # Usa a configuração de retentativa do decorator