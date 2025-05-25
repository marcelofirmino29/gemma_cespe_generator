# config/__init__.py

# Isso garante que o app Celery seja sempre importado quando o Django iniciar
# para que as tarefas compartilhadas (@shared_task) usem este app.
from .celery import app as celery_app

__all__ = ('celery_app',)