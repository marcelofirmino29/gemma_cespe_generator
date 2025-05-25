# config/celery.py
import os
from celery import Celery
from celery.schedules import crontab, timedelta # Adicione timedelta se for usar

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'run-pci-scraper-expanded-collection-test': { # Nome ajustado para indicar que é para teste
        'task': 'generator.tasks.run_pci_scraper_task',
        # AGENDAMENTO PARA TESTE: Rodar a cada 2 minutos.
        # Você pode ajustar para '*/1' para a cada minuto, ou timedelta(seconds=X) para mais rápido.
        'schedule': crontab(minute='*/2'),
        # 'schedule': timedelta(minutes=1), # Alternativa: a cada 1 minuto
        'kwargs': {
            "max_categorias_cargo": 5,        # Processar as primeiras 5 categorias
            "max_paginas_por_categoria": 2,    # Processar até 2 páginas por categoria
            "ano_alvo": None,                  # Coletar provas de TODOS os anos
            "max_profundidade_recursao": 1,    # Explorar sub-listagens até 1 nível de profundidade
        },
        'options': { # Opcional: define um tempo limite para a tarefa (ex: 1 hora)
            'expires': 3600, # Em segundos
        }
    },
    # Você pode comentar ou remover a entrada antiga do schedule se esta for substituí-la
    # 'run-pci-scraper-daily-at-3am': {
    #     'task': 'generator.tasks.run_pci_scraper_task',
    #     'schedule': crontab(hour=3, minute=0),
    #     'kwargs': {
    #         "max_categorias_cargo": 10, # Ou os valores de produção que você deseja
    #         "max_paginas_por_categoria": 3,
    #         "ano_alvo": None,
    #         "max_profundidade_recursao": 1,
    #     },
    # },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    # Em vez de print, use o logger do Celery para consistência
    # import logging
    # logger = logging.getLogger(__name__)
    # logger.info(f'Request: {self.request!r}')
    print(f'DEBUG TASK EXECUTED - Request: {self.request!r}') # Mantido print para simplicidade do debug_task
    return "Debug task executed."