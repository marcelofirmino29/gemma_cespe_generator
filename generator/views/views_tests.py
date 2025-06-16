# generator/views/views_tests.py

from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from datetime import datetime
import logging

# A importação de 'DiscursiveAnswerForm' foi removida da lista abaixo
from generator.forms import (
    QuestionGeneratorForm, DiscursiveExamForm, AskAIForm,
    AreaConhecimentoForm, CustomUserCreationForm, SimuladoConfigForm, PDFUploadForm
)
from generator.services import QuestionGenerationService
from generator.exceptions import (
    GeneratorError, ConfigurationError, AIServiceError, AIResponseError, ParsingError
)
from generator.utils import parse_evaluation_scores
from generator.models import Questao, AreaConhecimento, TentativaResposta, Avaliacao
from django.db.models import Q


logger = logging.getLogger(__name__)


# --- FUNÇÃO DE TESTE (Mantida) ---
@login_required
def test_print_view(request):
    """View simples para testes rápidos de log e resposta."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f">>> TESTE PRINT VIEW EXECUTADO por {request.user.username} em {now_str} <<<"
    print(message) # Imprime no console onde o Django está rodando
    logger.info(f">>> Log INFO test_print_view (User: {request.user.username})")
    logger.warning(">>> Log WARNING test_print_view")
    logger.error(">>> Log ERROR test_print_view (apenas para teste)")
    # Retorna uma resposta HTTP simples para o navegador
    return HttpResponse(f"<h1>Teste Concluído</h1><p>{message}</p><p>Logado como: {request.user.username}</p><p>Verifique o console e os logs do Django.</p>")

# Restante do arquivo (que está comentado) permanece igual.
# ...
# ...