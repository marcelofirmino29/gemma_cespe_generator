# generator/views.py

# Imports necessários para AMBAS as views
from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import timezone
import logging
import datetime # Pode ser necessário se timezone não cobrir seu formato

# Imports específicos do seu app
from .forms import QuestionGeneratorForm
from .services import QuestionGenerationService
from .exceptions import (
    GeneratorError, ConfigurationError, AIServiceError,
    AIResponseError, ParsingError
)

# Configuração do Logger (use um nome consistente)
logger = logging.getLogger('generator')

# ======================================================================
#  VIEW PARA GERAR QUESTÕES (Original que você compartilhou)
# ======================================================================
# Cole APENAS esta função modificada, substituindo a existente
# generate_questions_view no seu arquivo generator/views.py

# ======================================================================
#  VIEW PARA GERAR QUESTÕES (COM LOGS DE DEBUG ADICIONAIS)
# ======================================================================
# Substitua generate_questions_view por esta versão que loga form.errors

# Substitua generate_questions_view por esta versão com MAIS prints

# Substitua generate_questions_view por esta versão CORRIGIDA (remove check action=='generate')

def generate_questions_view(request):
    # Mantém a inicialização do form para GET
    form = QuestionGeneratorForm(request.POST or None, max_questions=settings.AI_MAX_QUESTIONS_PER_REQUEST)
    generated_questions = None
    error_message = None
    service_initialized = True
    context = {}

    # --- Bloco de Inicialização do Serviço e Hora Local (MANTENHA COMO ESTAVA) ---
    try: service = QuestionGenerationService(); logger.info(">>> QuestionGenerationService inicializado (usando logger)")
    except ConfigurationError as e: logger.critical(f">>> Falha CRÍTICA config: {e}", exc_info=True); error_message = "Erro config IA."; service = None; service_initialized = False
    except Exception as e: logger.critical(f">>> Falha inesperada init: {e}", exc_info=True); error_message = "Erro inesperado init."; service = None; service_initialized = False
    context['service_initialized'] = service_initialized
    context['error_message'] = error_message
    try: local_time_now = timezone.localtime(timezone.now()); context['local_time'] = local_time_now.strftime('%d/%m/%Y %H:%M:%S %Z')
    except Exception: context['local_time'] = "N/A"
    # --- Fim Bloco Inicialização ---

    # Processamento do POST
    if request.method == 'POST' and service_initialized and service:
        # Recria o form com dados POST para validação
        form = QuestionGeneratorForm(request.POST, max_questions=settings.AI_MAX_QUESTIONS_PER_REQUEST)
        print(f"\n--- [POST Recebido] ---") # PRINT (Action removida)

        # REMOVIDO: if action == 'generate':
        # AGORA: Se for POST e form for válido, tenta gerar.
        is_valid = form.is_valid()
        print(f"--- Verificando formulário... form.is_valid() = {is_valid} ---") # PRINT

        if is_valid: # Verifica se é válido
            topic = form.cleaned_data['topic']
            num_questions = form.cleaned_data['num_questions']
            logger.info(f">>> Formulário válido. Solicitando {num_questions}q para '{topic[:80]}...'")

            try:
                print(f"--- Chamando service.generate_questions com topico='{topic}' e num_questions={num_questions} ---") # PRINT
                generated_questions = service.generate_questions(topic, num_questions)
                print(f"--- Serviço retornou: {generated_questions} ---") # PRINT (ESSENCIAL!)

                if not generated_questions:
                    logger.warning(f">>> Serviço retornou vazio/None para '{topic}'.")
                    context['error_message'] = "A IA processou, mas não retornou questões utilizáveis."
                else:
                     logger.info(f">>> Questões geradas: {len(generated_questions)}.")
                     context['error_message'] = None # Limpa erro
            # --- Blocos except (mantidos) ---
            except AIResponseError as e: logger.warning(f">>> Erro AIResponseError: {e}"); context['error_message'] = f"Erro da IA: {e}"; generated_questions = None
            except ParsingError as e: logger.error(f">>> Erro ParsingError: {e}"); context['error_message'] = f"Erro ao processar resposta: {e}."; generated_questions = None
            except AIServiceError as e: logger.error(f">>> Erro AIServiceError: {e}", exc_info=True); context['error_message'] = f"Erro ao contatar IA: {e}."; generated_questions = None
            except GeneratorError as e: logger.error(f">>> Erro GeneratorError: {e}", exc_info=True); context['error_message'] = f"Erro interno geração: {e}"; generated_questions = None
            except Exception as e: logger.exception(f">>> Erro Inesperado GERAL: {e}"); context['error_message'] = "Erro inesperado servidor."; generated_questions = None
            # --- Fim Excepts ---

        else: # Se form.is_valid() for False
            logger.warning(">>> Tentativa com form inválido.")
            print(f"!!! FORM ERRORS (using print): {form.errors.as_json()} !!!") # PRINT
            context['error_message'] = "Corrija os erros no formulário."

    # Adiciona form e questões ao contexto final
    context['form'] = form # Passa o form (recriado no POST, pode ter erros)
    context['questions'] = generated_questions

    print(f"--- Contexto final para renderizar (sem action check): {context} ---") # PRINT
    return render(request, 'generator/question_generator.html', context)

# Mantenha validate_answers_view e test_print_view abaixo...

# Mantenha validate_answers_view e test_print_view abaixo...
# Mantenha a validate_answers_view abaixo...
# Certifique-se que a função validate_answers_view ainda existe abaixo desta no seu arquivo!


# ======================================================================
#  VIEW PARA VALIDAR RESPOSTAS (Última versão ajustada)
# ======================================================================
def validate_answers_view(request):
    """
    View para receber respostas do formulário, comparar com o gabarito
    e exibir o resultado no mesmo template.
    """
    context = {}
    service_initialized = True # Presume True, ajusta no try/except

    # Tentar inicializar o serviço para obter o status para o template
    try:
        QuestionGenerationService() # Instancia para checar config
        logger.info("Serviço verificado/inicializado em validate_answers_view.")
    except ConfigurationError as e:
        logger.critical(f"Falha CRÍTICA na configuração do serviço em validate_answers_view: {e}", exc_info=True)
        context['error_message'] = "Erro interno do servidor: Falha na configuração. Contate o administrador."
        service_initialized = False
    except Exception as e:
        logger.critical(f"Falha inesperada na inicialização do serviço em validate_answers_view: {e}", exc_info=True)
        context['error_message'] = "Erro inesperado na inicialização do serviço."
        service_initialized = False

    context['service_initialized'] = service_initialized

    # Adicionar hora local ao contexto sempre
    try:
        local_time_now = timezone.localtime(timezone.now())
        context['local_time'] = local_time_now.strftime('%d/%m/%Y %H:%M:%S %Z')
    except Exception:
        context['local_time'] = "N/A" # Fallback

    if request.method == 'POST' and service_initialized:
        logger.info("validate_answers_view recebendo POST.")
        logger.debug(f"Dados recebidos: {request.POST}")

        results_list = []
        error_processing = None

        try:
            # Extrair dados baseado nos nomes do HTML (`resposta_N`, `afirmacao_N`, `gabarito_N`)
            items_to_process = {}
            # Encontra todos os índices enviados para garantir que processamos todos
            indices = sorted(list(set([int(k.split('_')[1]) for k in request.POST if k.startswith('index_')])))

            if not indices:
                 raise ValueError("Nenhum índice de questão encontrado no POST.")

            for index in indices:
                user_answer = request.POST.get(f'resposta_{index}')
                affirmation = request.POST.get(f'afirmacao_{index}')
                correct_answer = request.POST.get(f'gabarito_{index}')

                # Verifica se todos os dados necessários para este item estão presentes
                if user_answer is None or affirmation is None or correct_answer is None:
                    logger.warning(f"Dados ausentes para o item de índice {index}. Pulando.")
                    # Poderia adicionar um resultado indicando falha aqui se desejado
                    continue

                # Realizar a validação simples (comparação direta)
                is_correct = (user_answer.strip().upper() == correct_answer.strip().upper())

                # Adicionar ao dicionário de resultados estruturados
                items_to_process[index] = {
                    'index': index,
                    'afirmacao': affirmation,
                    'user_answer': user_answer, # Resposta como veio ('C' ou 'E')
                    'gabarito': correct_answer, # Gabarito como veio ('C' ou 'E')
                    'correct': is_correct # Boolean
                }

            # Ordenar os resultados pela ordem original (índice)
            results_list = [items_to_process[i] for i in indices if i in items_to_process]

            if not results_list and indices: # Se tínhamos índices mas nenhum foi processado
                 logger.error("Nenhum item pôde ser processado após a validação dos dados, embora índices estivessem presentes.")
                 error_processing = "Não foi possível processar os dados de nenhum item. Verifique o envio."
            elif not indices: # Caso redundante devido ao raise anterior, mas seguro
                 logger.warning("Nenhum índice encontrado para processar.")
                 # Não definir erro aqui, pois o raise já foi tratado
            else:
                 logger.info(f"Processados {len(results_list)} itens para resultado.")


        except ValueError as e:
            logger.error(f"Erro ao processar dados do formulário de validação: {e}", exc_info=True)
            error_processing = f"Erro ao processar os dados: {e}." # Mensagem mais amigável
        except Exception as e:
            logger.exception(f"Erro inesperado durante o processamento da validação: {e}")
            error_processing = "Ocorreu um erro inesperado ao processar suas respostas."

        # Preparar contexto para renderizar o MESMO template, mas com 'results'
        context['results'] = results_list # Passa a lista de resultados
        # Atualiza a msg de erro SE houve erro no processamento, senão mantém o da inicialização (se houver)
        if error_processing:
             context['error_message'] = error_processing

        # Passar uma instância vazia do formulário de geração
        context['form'] = QuestionGeneratorForm()
        # Não passamos 'questions', apenas 'results'

        # Renderizar o template original, ativando a seção {% if results %}
        return render(request, 'generator/question_generator.html', context)

    elif request.method == 'GET':
        # Se alguém acessar a URL de validação diretamente via GET, redireciona para a página inicial
        logger.info("Acesso GET a validate_answers_view, redirecionando para generate_questions.")
        return redirect('generate_questions') # Redireciona para a view de GERAÇÃO

    else: # POST mas serviço não inicializado
         logger.error("Tentativa de POST em validate_answers_view com serviço não inicializado.")
         # Renderiza a página com o erro de inicialização já no contexto
         context['form'] = QuestionGeneratorForm() # Passa um form vazio também
         return render(request, 'generator/question_generator.html', context)
    
    # Adicione esta função ao FINAL do seu generator/views.py

from django.http import HttpResponse # Adicione este import no TOPO do arquivo se já não estiver lá

def test_print_view(request):
    message = ">>> TESTE PRINT VIEW FOI EXECUTADO! <<<"
    print(message) # Comando print direto para o terminal
    logger.info(">>> Log INFO da test_print_view (via logger)") # Testa o logger também
    return HttpResponse(f"<h1>Teste Concluído</h1><p>{message}</p><p>Verifique o terminal onde 'runserver' está rodando.</p>")