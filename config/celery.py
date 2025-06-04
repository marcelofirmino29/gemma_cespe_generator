# config/celery.py
import os
from celery import Celery
from celery.schedules import crontab, timedelta # Importa timedelta
import datetime # Para usar no ano_alvo

# Define o módulo de settings padrão do Django para o 'celery'.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Usa uma string aqui significa que o worker não precisa serializar
# o objeto de configuração para processos filhos.
# - namespace='CELERY' significa todas as configs do Celery devem ter um prefixo `CELERY_`
app.config_from_object('django.conf:settings', namespace='CELERY')

# Carrega módulos task.py de todos os apps Django registrados.
app.autodiscover_tasks()

# --- IMPORTANTE SOBRE DJANGO-CELERY-BEAT e DatabaseScheduler ---
# Quando você usa django_celery_beat.schedulers:DatabaseScheduler, as tarefas agendadas
# aqui em app.conf.beat_schedule são sincronizadas com o banco de dados UMA VEZ
# na primeira vez que o Beat inicia ou quando o Beat deteta alterações neste ficheiro
# (o que pode não ser imediato ou fiável para atualizações subsequentes).
#
# APÓS A PRIMEIRA SINCRONIZAÇÃO, O BANCO DE DADOS É A FONTE DA VERDADE.
#
# Para alterar, desabilitar ou adicionar novas tarefas periódicas de forma fiável
# após a primeira execução, você DEVE FAZÊ-LO ATRAVÉS DO PAINEL DE ADMINISTRAÇÃO DO DJANGO
# (na secção "Periodic Tasks" ou "Tarefas Periódicas" do app Django Celery Beat).
#
# Comentar ou alterar tarefas aqui pode não ter efeito em tarefas já existentes no banco de dados
# até que você as remova/modifique no admin e reinicie o Beat.
# Para forçar uma nova sincronização, pode ser necessário limpar as tabelas do django_celery_beat
# ou gerir as tarefas exclusivamente pelo Admin após a configuração inicial.

app.conf.beat_schedule = {
    # Tarefa do scraper PCI - Mantida como diária para produção
    'run-pci-scraper-task-daily-production': {
        'task': 'generator.tasks.run_pci_scraper_task',
        'schedule': crontab(hour=3, minute=0), # Roda diariamente às 3:00 AM
        'kwargs': {
            "max_categorias_cargo": 20, # Pode aumentar para produção
            "max_paginas_por_categoria": 10, # Pode aumentar para produção
            "ano_alvo": datetime.date.today().year, # Processa o ano corrente
            "max_profundidade_recursao": 2, # Profundidade maior para mais detalhes
        },
        'options': {
            'expires': 3600 * 6, # Expira em 6 horas
        },
        'enabled': True, # Certifique-se que está ativa no Admin do Django
    },

    # Tarefa de TESTE para o scraper PCI - Roda a cada 5 minutos
    # USE ESTA PARA TESTES. DESABILITE OU REMOVA NO ADMIN QUANDO NÃO PRECISAR.
    'run-pci-scraper-task-testing-every-5-minutes': {
        'task': 'generator.tasks.run_pci_scraper_task',
        'schedule': crontab(minute='*/5'), # Roda a cada 5 minutos
        'kwargs': {
            "max_categorias_cargo": 2,    # <<< Limite baixo para teste rápido
            "max_paginas_por_categoria": 1, # <<< Limite baixo para teste rápido
            "ano_alvo": datetime.date.today().year,
            "max_profundidade_recursao": 1,
        },
        'options': {
            'expires': 600, # Expira em 10 minutos
        },
        'enabled': True, # ATIVE NO ADMIN DO DJANGO PARA TESTAR
                         # ou defina como False aqui e ative no Admin.
    },

    # Tarefa de teste para o scraper do Planalto - COMENTADA
    # Se precisar testar, descomente e ajuste, ou, preferencialmente,
    # crie/ative uma tarefa para ele no Admin do Django.
    # 'run-planalto-leis-scraper-test-hourly': {
    #     'task': 'generator.tasks.scrape_planalto_laws_task',
    #     'schedule': crontab(minute='0'), # Roda no início de cada hora
    #     'kwargs': {
    #         "max_depth": 1,
    #     },
    #     'options': {
    #         'expires': 3600 * 2,
    #     },
    #     'enabled': False, # Desabilitada por defeito no código
    # },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'DEBUG TASK EXECUTED - Request: {self.request!r}')
    return "Debug task executed."