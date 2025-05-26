# config/celery.py
import os
from celery import Celery
from celery.schedules import crontab, timedelta # Certifique-se que timedelta está importado

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'run-planalto-leis-scraper-test-now': { # Nome para o teste
        'task': 'generator.tasks.scrape_planalto_laws_task',
        'schedule': timedelta(seconds=30), # <<< Roda 30 segundos após o Beat iniciar
        'kwargs': {
            "max_depth": 6, # <<<< PROFUNDIDADE MUITO BAIXA PARA TESTE INICIAL RÁPIDO
                            # Aumente para 1 se a página inicial não for uma lei.
            # "start_url": "https://www.planalto.gov.br/ccivil_03/Constituicao/Constituicao.htm" # Opcional: URL específica para teste
        },
        'options': {
            'expires': 3600 * 1, # Expira em 1 hora
        }
    },
    # Comente a tarefa do PCI temporariamente para focar no teste do scraper de leis
    # 'run-pci-scraper-task-daily': {
    #     'task': 'generator.tasks.run_pci_scraper_task',
    #     'schedule': crontab(hour=3, minute=0),
    #     'kwargs': {
    #         "max_categorias_cargo": 10,
    #         "max_paginas_por_categoria": 5,
    #         "ano_alvo": None,
    #         "max_profundidade_recursao": 1,
    #     },
    # },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'DEBUG TASK EXECUTED - Request: {self.request!r}')
    return "Debug task executed."