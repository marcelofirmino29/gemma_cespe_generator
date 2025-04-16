# generator/views.py

# Imports necessários para AMBAS as views
from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import timezone
import logging
import datetime # Pode ser necessário se timezone não cobrir seu formato
import math # Importado para usar round() ou outras funções se necessário

# Imports específicos do seu app
from .forms import QuestionGeneratorForm
from .services import QuestionGenerationService # Garanta que este serviço aceite difficulty_level
from .exceptions import (
    GeneratorError, ConfigurationError, AIServiceError,
    AIResponseError, ParsingError
)

# Imports para test_print_view
from django.http import HttpResponse # Adicionado para test_print_view

logger = logging.getLogger('generator')

# --- Função generate_questions_view (mantida como na última versão) ---
def generate_questions_view(request):
    # Mantém a inicialização do form para GET
    # Passa None se for GET, request.POST se for POST
    form = QuestionGeneratorForm(request.POST or None, max_questions=settings.AI_MAX_QUESTIONS_PER_REQUEST)
    generated_questions = None
    error_message = None
    service_initialized = True
    context = {}

    # --- Bloco de Inicialização do Serviço e Hora Local ---
    try:
        service = QuestionGenerationService()
        logger.info(">>> QuestionGenerationService inicializado (usando logger)")
    except ConfigurationError as e:
        logger.critical(f">>> Falha CRÍTICA config: {e}", exc_info=True)
        error_message = "Erro de configuração interna do servidor. Tente novamente mais tarde."
        service = None
        service_initialized = False
    except Exception as e:
        logger.critical(f">>> Falha inesperada na inicialização do serviço: {e}", exc_info=True)
        error_message = "Erro inesperado na inicialização do servidor."
        service = None
        service_initialized = False

    context['service_initialized'] = service_initialized
    # Define a mensagem de erro inicial APENAS se houver erro na inicialização
    if error_message:
        context['error_message'] = error_message

    # Adicionar hora local ao contexto sempre
    try:
        # Presumindo que settings.TIME_ZONE está configurado corretamente (ex: 'America/Boa_Vista')
        local_time_now = timezone.localtime(timezone.now())
        # Usando o formato brasileiro comum e incluindo o fuso horário
        context['local_time'] = local_time_now.strftime('%d/%m/%Y %H:%M:%S %Z')
    except Exception as e:
        logger.error(f"Erro ao obter hora local: {e}")
        context['local_time'] = "N/A" # Fallback
    # --- Fim Bloco Inicialização ---

    # Processamento do POST
    if request.method == 'POST' and service_initialized and service:
        # form já foi instanciado com request.POST no início
        print(f"\n--- [POST Recebido em generate_questions_view] ---") # PRINT

        is_valid = form.is_valid() # Valida o formulário preenchido com request.POST
        print(f"--- Verificando formulário... form.is_valid() = {is_valid} ---") # PRINT

        if is_valid: # Verifica se é válido
            topic = form.cleaned_data['topic']
            num_questions = form.cleaned_data['num_questions']
            difficulty = form.cleaned_data['difficulty_level']

            logger.info(f">>> Formulário válido. Solicitando {num_questions}q [{difficulty}] para '{topic[:80]}...'")

            try:
                print(f"--- Chamando service.generate_questions com topico='{topic}', num_questions={num_questions}, difficulty='{difficulty}' ---") # PRINT
                generated_questions = service.generate_questions(
                    topic,
                    num_questions,
                    difficulty_level=difficulty # Passa como argumento nomeado
                )
                print(f"--- Serviço retornou: {generated_questions} ---") # PRINT (ESSENCIAL!)

                if not generated_questions:
                    logger.warning(f">>> Serviço retornou vazio/None para '{topic}' [{difficulty}].")
                    context['error_message'] = "A IA processou sua solicitação, mas não conseguiu gerar questões válidas para este tópico/dificuldade. Tente ser mais específico ou alterar a dificuldade."
                else:
                     logger.info(f">>> Questões geradas com sucesso: {len(generated_questions)}.")
                     context['error_message'] = None # Limpa erro se sucesso

            # Blocos except (mantidos como antes)
            except AIResponseError as e: logger.warning(f">>> Erro AIResponseError ({topic}[{difficulty}]): {e}"); context['error_message'] = f"Erro na resposta da IA: {e}"; generated_questions = None
            except ParsingError as e: logger.error(f">>> Erro ParsingError ({topic}[{difficulty}]): {e}", exc_info=True); context['error_message'] = f"Erro ao processar a resposta da IA: {e}."; generated_questions = None
            except AIServiceError as e: logger.error(f">>> Erro AIServiceError ({topic}[{difficulty}]): {e}", exc_info=True); context['error_message'] = f"Erro ao contatar o serviço de IA: {e}. Verifique sua conexão ou tente mais tarde."; generated_questions = None
            except GeneratorError as e: logger.error(f">>> Erro GeneratorError ({topic}[{difficulty}]): {e}", exc_info=True); context['error_message'] = f"Erro interno na geração das questões: {e}"; generated_questions = None
            except Exception as e: logger.exception(f">>> Erro Inesperado GERAL durante geração ({topic}[{difficulty}]): {e}"); context['error_message'] = "Ocorreu um erro inesperado no servidor ao gerar as questões."; generated_questions = None

        else: # Se form.is_valid() for False
            logger.warning(">>> Tentativa de geração com formulário inválido.")
            print(f"!!! FORM ERRORS (using print): {form.errors.as_json()} !!!") # PRINT
            first_error_key = next(iter(form.errors), None)
            if first_error_key:
                # Acessa o label do campo para uma mensagem mais amigável
                field_label = form[first_error_key].label
                context['error_message'] = f"Erro no campo '{field_label}': {form.errors[first_error_key].as_text()}"
            else:
                 context['error_message'] = "Corrija os erros no formulário." # Fallback

    # Adiciona form e questões ao contexto final, APÓS todo o processamento
    context['form'] = form
    context['questions'] = generated_questions

    print(f"--- Contexto final (generate_questions_view): { {k: v for k, v in context.items() if k != 'questions'} } ---")
    return render(request, 'generator/question_generator.html', context)


# --- Função validate_answers_view (MODIFICADA para incluir cálculo de % e flag) ---
def validate_answers_view(request):
    """
    View para receber respostas, comparar, calcular desempenho (incluindo % e flag)
    e exibir o resultado.
    """
    context = {}
    service_initialized = True # Presume True, ajusta no try/except

    # Tentar inicializar o serviço para obter o status para o template
    try:
        QuestionGenerationService() # Instancia para checar config
        logger.info("Serviço verificado/inicializado em validate_answers_view.")
    except ConfigurationError as e:
        logger.critical(f"Falha CRÍTICA config em validate_answers_view: {e}", exc_info=True)
        context['error_message'] = "Erro interno: Falha na configuração. Não é possível validar."
        service_initialized = False
    except Exception as e:
        logger.critical(f"Falha inesperada init em validate_answers_view: {e}", exc_info=True)
        context['error_message'] = "Erro inesperado na inicialização. Não é possível validar."
        service_initialized = False

    context['service_initialized'] = service_initialized

    # Adicionar hora local ao contexto sempre
    try:
        local_time_now = timezone.localtime(timezone.now())
        context['local_time'] = local_time_now.strftime('%d/%m/%Y %H:%M:%S %Z')
    except Exception as e:
        logger.error(f"Erro ao obter hora local (validate): {e}")
        context['local_time'] = "N/A" # Fallback

    # Processa apenas se for POST e o serviço estiver OK
    if request.method == 'POST' and service_initialized:
        logger.info("validate_answers_view recebendo POST.")
        logger.debug(f"Dados recebidos: {request.POST}")

        results_list = []
        error_processing = None
        performance_data = None # Inicializa dados de performance como None

        try:
            # Extrair dados do POST
            items_to_process = {}
            indices = sorted(list(set([int(k.split('_')[1]) for k in request.POST if k.startswith('index_')])))

            if not indices:
                 raise ValueError("Nenhum índice de questão encontrado nos dados enviados.")

            for index in indices:
                user_answer = request.POST.get(f'resposta_{index}')
                affirmation = request.POST.get(f'afirmacao_{index}')
                correct_answer = request.POST.get(f'gabarito_{index}')

                # Validação mais robusta dos dados recebidos
                if user_answer is None or not isinstance(user_answer, str) or user_answer.strip().upper() not in ['C', 'E']:
                     logger.warning(f"Resposta inválida ou ausente para o item {index}. Pulando.")
                     continue # Pula este item se a resposta não for C ou E
                if affirmation is None or not isinstance(affirmation, str) or not affirmation.strip():
                     logger.warning(f"Afirmação ausente ou inválida para o item {index}. Pulando.")
                     continue # Pula se a afirmação estiver faltando
                if correct_answer is None or not isinstance(correct_answer, str) or correct_answer.strip().upper() not in ['C', 'E']:
                     logger.warning(f"Gabarito ausente ou inválido ('{correct_answer}') para o item {index}. Pulando.")
                     continue # Pula se o gabarito não for C ou E


                is_correct = (user_answer.strip().upper() == correct_answer.strip().upper())

                items_to_process[index] = {
                    'index': index,
                    'afirmacao': affirmation.strip(), # Garante sem espaços extras
                    'user_answer': user_answer.strip().upper(),
                    'gabarito': correct_answer.strip().upper(),
                    'correct': is_correct
                }

            # Ordenar os resultados pela ordem original
            results_list = [items_to_process[i] for i in indices if i in items_to_process]

            # Verifica se algum item foi processado antes de calcular performance
            if not results_list:
                 if indices: logger.error("Nenhum item pôde ser processado após a validação dos dados.")
                 else: logger.warning("Nenhum índice válido encontrado para processar.")
                 error_processing = "Não foi possível processar os dados de nenhum item. Verifique o envio ou se os itens eram válidos."
            else:
                 logger.info(f"Processados {len(results_list)} itens para resultado detalhado.")

                 # ========== INÍCIO: Cálculo do Desempenho (Incluindo % e flag) ==========
                 correct_count = 0
                 incorrect_count = 0
                 total_questions = len(results_list) # Número de questões válidas processadas

                 for result in results_list:
                     if result.get('correct', False):
                         correct_count += 1
                     else:
                         incorrect_count += 1

                 final_score = correct_count - incorrect_count

                 # --- Calcular porcentagem e flag ---
                 percentage_correct = 0 # Porcentagem de acertos (0 a 100)
                 more_than_half_score = False # Flag se score > metade do máximo possível

                 if total_questions > 0:
                     percentage_correct = round((correct_count / total_questions) * 100)
                     # Verifica se a pontuação líquida é maior que metade da pontuação máxima possível
                     more_than_half_score = (final_score > (total_questions / 2.0)) # Usa 2.0 para garantir float division
                 # --- Fim Cálculo Adicional ---

                 performance_data = {
                     'correct': correct_count,
                     'incorrect': incorrect_count,
                     'total': total_questions,
                     'score': final_score,
                     # --- Adicionar dados calculados ---
                     'percentage': percentage_correct,
                     'more_than_half': more_than_half_score
                     # --- Fim Adição ---
                 }
                 logger.info(f"Desempenho calculado: {correct_count} C, {incorrect_count} E. Score: {final_score}/{total_questions}. Acertos: {percentage_correct}%.")
                 # ========== FIM: Cálculo do Desempenho ==========

        except ValueError as e:
            logger.error(f"Erro ao processar dados (ValueError) em validate_answers_view: {e}", exc_info=True)
            error_processing = f"Erro ao processar os dados recebidos: {e}."
        except Exception as e:
            logger.exception(f"Erro inesperado durante processamento em validate_answers_view: {e}")
            error_processing = "Ocorreu um erro inesperado ao processar suas respostas."

        # --- Preparar contexto final para renderizar ---
        context['results'] = results_list
        if performance_data: context['performance'] = performance_data # Adiciona se calculado
        if error_processing: context['error_message'] = error_processing

        context['form'] = QuestionGeneratorForm() # Passa form vazio para nova geração

        print(f"--- Contexto final (validate_answers_view): { {k: v for k, v in context.items() if k not in ['results', 'performance']} } ---")
        return render(request, 'generator/question_generator.html', context)

    elif request.method == 'GET':
        # Redireciona para a página inicial se GET
        logger.info("Acesso GET a validate_answers_view, redirecionando para generate_questions.")
        return redirect('generate_questions') # Nome da URL pattern

    else: # POST mas serviço não inicializado
         logger.error("Tentativa de POST em validate_answers_view com serviço não inicializado.")
         context['form'] = QuestionGeneratorForm()
         return render(request, 'generator/question_generator.html', context)

# --- Função de Teste (Mantida como estava) ---
def test_print_view(request):
    message = ">>> TESTE PRINT VIEW FOI EXECUTADO! <<<"
    print(message) # Comando print direto para o terminal
    logger.info(">>> Log INFO da test_print_view (via logger)") # Testa o logger também
    return HttpResponse(f"<h1>Teste Concluído</h1><p>{message}</p><p>Verifique o terminal onde 'runserver' está rodando.</p>")