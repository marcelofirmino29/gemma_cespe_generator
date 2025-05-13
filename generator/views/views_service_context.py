from datetime import timezone
from venv import logger
from generator.exceptions import ConfigurationError
from generator.services import QuestionGenerationService

def _get_base_context_and_service():
    """Inicializa o serviço de IA e obtém o contexto base."""
    context = {}
    service = None
    service_initialized = True
    error_message = None
    try:
        service = QuestionGenerationService()
        logger.info(">>> Service inicializado.")
    except ConfigurationError as e:
        logger.critical(f">>> Falha config: {e}", exc_info=False)
        error_message = f"Erro config: {e}."
        service_initialized = False
    except Exception as e:
        logger.critical(f">>> Falha inesperada init: {e}", exc_info=True)
        error_message = f"Erro inesperado init IA: {e}"
        service_initialized = False

    context['service_initialized'] = service_initialized
    if error_message:
        context['error_message'] = error_message

    try:
        now_local = timezone.localtime(timezone.now())
        context['local_time'] = now_local.strftime('%d/%m/%Y %H:%M:%S %Z')
    except Exception:
        context['local_time'] = "N/A"

    return context, service if service_initialized else None, service_initialized
