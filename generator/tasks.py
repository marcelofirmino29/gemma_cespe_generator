# generator/tasks.py
from celery import shared_task, states
from celery.exceptions import Ignore
from django.conf import settings
import logging
import time

# Importe a FUNÇÃO principal do seu script de scraper
# Se o arquivo se chama scraper_provas_pci.py e está em generator/
try:
    from .scraper_provas_pci import scraper_pci_provas_principal
    # Se você adaptou scraper_provas_pci.py para salvar no BD e usar logging:
    # from .scraper_provas_pci import scraper_pci_provas_principal_com_bd_save
except ImportError as e:
    logging.error(f"Erro ao importar 'scraper_pci_provas_principal' de '.scraper_provas_pci': {e}")
    scraper_pci_provas_principal = None # Para evitar erro se o import falhar

# Se o seu script original (que salva em JSON e usa print) se chama scraper_logic.py:
# from .scraper_logic import scraper_pci_provas_principal as scraper_original_com_json

logger = logging.getLogger(__name__)

@shared_task(bind=True, name="generator.tasks.run_pci_scraper_task", max_retries=3, default_retry_delay=5*60)
def run_pci_scraper_task(self, **kwargs_from_beat_or_manual_call):
    task_id = self.request.id
    logger.info(f"[TASK_ID:{task_id}] Iniciando tarefa Celery run_pci_scraper_task com args: {kwargs_from_beat_or_manual_call}")

    if scraper_pci_provas_principal is None: # Ou o nome da função que você importou
        logger.error(f"[TASK_ID:{task_id}] A função do scraper não pôde ser importada. A tarefa não pode ser executada.")
        # Você pode querer que a tarefa falhe explicitamente aqui
        self.update_state(state=states.FAILURE, meta={'exc_type': 'ImportError', 'exc_message': 'Função do scraper não encontrada.'})
        raise Ignore() # Ignora a tarefa para não tentar novamente se a importação falhou

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
    # Remove chaves com valor None se a função do scraper não os espera ou os trata como default
    params_para_funcao_limpos = {k: v for k, v in params_para_funcao.items() if v is not None}


    logger.info(f"[TASK_ID:{task_id}] Parâmetros para a função do Scraper: {params_para_funcao_limpos}")

    try:
        time.sleep(2)
        # Chame a FUNÇÃO principal do seu scraper procedural
        # Certifique-se que esta função está adaptada para salvar no BD e usar logging
        dados_coletados = scraper_pci_provas_principal(**params_para_funcao_limpos)

        # Se a função scraper_pci_provas_principal já salva no BD e loga,
        # você pode apenas logar o sucesso aqui.
        # Se ela retornar os dados para serem salvos pela task, você faria o salvamento aqui.

        success_message = f"[TASK_ID:{task_id}] Tarefa Celery run_pci_scraper_task (chamando função procedural) concluída."
        if dados_coletados: # Se a função retornar os dados
             logger.info(f"{success_message} {len(dados_coletados)} itens processados.")
        else:
             logger.info(f"{success_message} Nenhum item processado ou função não retorna dados.")
        return success_message
    except Exception as exc:
        logger.error(f"[TASK_ID:{task_id}] Erro na tarefa Celery run_pci_scraper_task (chamando função procedural): {exc}", exc_info=True)
        raise self.retry(exc=exc) # Usa a configuração de retentativa do decorator