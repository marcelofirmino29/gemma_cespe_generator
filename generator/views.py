# generator/views.py (VERSÃO FINAL CHAMANDO PARSER EXTERNO CORRETAMENTE)

from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import timezone
import logging
import datetime
# import re # Removido daqui pois o parsing está em utils.py
from django.http import HttpResponse

# Importa TODOS os formulários necessários
from .forms import QuestionGeneratorForm, DiscursiveAnswerForm, DiscursiveExamForm
# Importa o serviço e as exceções necessárias
from .services import QuestionGenerationService
from .exceptions import (
    GeneratorError, ConfigurationError, AIServiceError,
    AIResponseError, ParsingError
)
# <<< PASSO 1: Import Descomentado e Ativo >>>
# Garanta que o arquivo generator/utils.py existe e contém a função!
from .utils import parse_evaluation_scores

logger = logging.getLogger('generator')

# --- Função Auxiliar (Mantida) ---
def _get_base_context_and_service():
    context = {}
    service = None
    service_initialized = True
    error_message = None
    try:
        service = QuestionGenerationService()
        logger.info(">>> QuestionGenerationService inicializado com sucesso na verificação.")
    except ConfigurationError as e:
        logger.critical(f">>> Falha CRÍTICA de configuração: {e}", exc_info=False)
        error_message = f"Erro crítico de configuração: {e}."
        service_initialized = False
    except Exception as e:
        logger.critical(f">>> Falha inesperada na inicialização serviço: {e}", exc_info=True)
        error_message = f"Erro inesperado inicializar serviço IA: {e}"
        service_initialized = False
    context['service_initialized'] = service_initialized
    if error_message: context['error_message'] = error_message
    try:
        now_local = timezone.localtime(timezone.now())
        context['local_time'] = now_local.strftime('%d/%m/%Y %H:%M:%S %Z')
    except Exception: context['local_time'] = "N/A"
    return context, service if service_initialized else None, service_initialized


# --- VISÃO LANDING PAGE (Mantida) ---
def landing_page_view(request):
    context, _, service_initialized = _get_base_context_and_service()
    context['error_message'] = context.get('error_message')
    return render(request, 'generator/landing_page.html', context)


# --- VISÃO GERADOR QUESTÕES C/E (Mantida) ---
def generate_questions_view(request):
    context, service, service_initialized = _get_base_context_and_service()
    generated_questions = None
    max_q = getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 5)
    form = QuestionGeneratorForm(request.POST or None, max_questions=max_q)
    context['form'] = form
    context['error_message'] = context.get('error_message')
    if request.method == 'POST':
        if not service_initialized or not service: logger.error("POST generate_questions_view s/ serviço IA."); context['error_message'] = context.get('error_message', "Serviço IA indisponível.")
        else:
            logger.info("POST generate_questions_view (C/E Tópico)")
            if form.is_valid():
                topic_text = form.cleaned_data.get('topic')
                num_questions = form.cleaned_data.get('num_questions')
                difficulty = form.cleaned_data.get('difficulty_level')
                form_valid_for_api = True
                if not topic_text or not topic_text.strip(): form.add_error('topic', 'Obrigatório.'); form_valid_for_api = False
                if num_questions is None: form.add_error('num_questions', 'Obrigatório.'); form_valid_for_api = False
                if not difficulty or not difficulty.strip(): form.add_error('difficulty_level', 'Obrigatório.'); form_valid_for_api = False
                if not form_valid_for_api: logger.warning("Geração Q C/E Tópico c/ campo obrigatório ausente."); context['error_message'] = "Erro formulário: Verifique campos obrigatórios."
                else:
                    logger.info(f"Form Q C/E válido API. Solicitando {num_questions}q [{difficulty}] TÓPICO: '{topic_text[:80]}...'")
                    try:
                        # A view chama o serviço, o serviço chama a IA e depois o parser INTERNO dele
                        generated_questions = service.generate_questions(topic=topic_text, num_questions=num_questions, difficulty_level=difficulty)
                        if not generated_questions: logger.warning("Serviço Q C/E Tópico retornou vazio."); context['error_message'] = "IA não retornou questões válidas."
                        else: logger.info(f"Questões C/E Tópico geradas: {len(generated_questions)}."); context['error_message'] = None
                    except ParsingError as e: # Erro específico do parser do Serviço para C/E
                         logger.error(f"Erro de PARSING INTERNO (C/E) vindo do Serviço: {e}", exc_info=True)
                         context['error_message'] = f"Erro ao processar resposta da IA (C/E): {e}"
                    except (AIResponseError, AIServiceError, GeneratorError, ConfigurationError, Exception) as e:
                        logger.error(f"Erro GERAL na geração Q C/E Tópico: {e}", exc_info=True); context['error_message'] = f"Falha gerar questões: {e}"
            else: logger.warning("Tentativa Geração Q C/E Tópico form inválido."); context['error_message'] = "Formulário inválido. Corrija erros."
    context['questions'] = generated_questions
    logger.debug(f"Contexto final (generate_questions_view): { {k: v for k, v in context.items() if k not in ['questions', 'form']} }")
    return render(request, 'generator/question_generator.html', context)


# --- VISÃO VALIDAR RESPOSTAS C/E (Mantida) ---
def validate_answers_view(request):
    # ... (código como antes, sem alterações significativas necessárias aqui) ...
    context, _, _ = _get_base_context_and_service()
    performance_data = None; results_list = []; error_processing = None
    context['form'] = QuestionGeneratorForm(max_questions=getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 5))
    if request.method == 'POST':
        logger.info("POST validate_answers_view")
        try:
            items_to_process = {}
            all_post_keys = request.POST.keys()
            indices = sorted(list(set([int(k.split('_')[1]) for k in all_post_keys if k.startswith('index_')])))
            if not indices: raise ValueError("Nenhum índice questão POST.")
            for index in indices:
                user_answer = request.POST.get(f'resposta_{index}')
                affirmation = request.POST.get(f'afirmacao_{index}')
                correct_answer = request.POST.get(f'gabarito_{index}')
                justification = request.POST.get(f'justificativa_{index}', 'N/A.')
                if user_answer is None or user_answer.strip().upper() not in ['C', 'E']: logger.warning(f"Idx {index}: Resp. inválida ('{user_answer}'). Ignorado."); continue
                if affirmation is None or not affirmation.strip(): logger.warning(f"Idx {index}: Afirmação vazia. Ignorado."); continue
                if correct_answer is None or correct_answer.strip().upper() not in ['C', 'E']: logger.warning(f"Idx {index}: Gabarito inválido ('{correct_answer}'). Ignorado."); continue
                if not isinstance(justification, str): logger.warning(f"Idx {index}: Justif. formato inválido."); justification = 'Inválido.'
                is_correct = (user_answer.strip().upper() == correct_answer.strip().upper())
                items_to_process[index] = { 'index': index, 'afirmacao': affirmation.strip(), 'user_answer': user_answer.strip().upper(), 'gabarito': correct_answer.strip().upper(), 'correct': is_correct, 'justificativa': justification.strip() }
            results_list = [items_to_process[i] for i in indices if i in items_to_process]
            if not results_list: error_processing = "Nenhum item válido processado."
            else:
                 logger.info(f"Processados {len(results_list)} itens p/ validação.")
                 correct_count = sum(1 for r in results_list if r.get('correct'))
                 incorrect_count = len(results_list) - correct_count; total_questions = len(results_list)
                 final_score = correct_count - incorrect_count
                 percentage_correct = round((correct_count / total_questions) * 100) if total_questions > 0 else 0
                 performance_data = { 'correct': correct_count, 'incorrect': incorrect_count, 'total': total_questions, 'score': final_score, 'percentage': percentage_correct }
                 logger.info(f"Desempenho: {correct_count} C, {incorrect_count} E. Score: {final_score}/{total_questions}.")
        except ValueError as e: logger.error(f"Erro ValueError validate: {e}", exc_info=True); error_processing = f"Erro dados: {e}."
        except Exception as e: logger.exception(f"Erro Exception validate: {e}"); error_processing = "Erro inesperado."
        context['results'] = results_list
        if performance_data: context['performance'] = performance_data
        if error_processing: context['error_message'] = error_processing
        logger.debug(f"Contexto final (validate_answers_view): { {k: v for k, v in context.items() if k not in ['results', 'performance', 'form']} }")
        return render(request, 'generator/question_generator.html', context)
    elif request.method == 'GET': return redirect('landing_page')
    context['error_message'] = context.get('error_message', "Acesso inválido.")
    return render(request, 'generator/question_generator.html', context)


# --- VISÃO GERAR RESPOSTA DISCURSIVA (Mantida) ---
def generate_discursive_view(request):
    # ... (código como antes) ...
    context, service, service_initialized = _get_base_context_and_service()
    essay_answer = None
    form = DiscursiveAnswerForm(request.POST or None)
    context['form'] = form
    context['error_message'] = context.get('error_message')
    if request.method == 'POST':
        if not service_initialized or not service: logger.error("POST generate_discursive_view s/ serviço IA."); context['error_message'] = context.get('error_message', "Serviço IA indisponível.")
        else:
            logger.info("POST generate_discursive_view")
            if form.is_valid():
                essay_prompt = form.cleaned_data.get('essay_prompt')
                key_points = form.cleaned_data.get('key_points')
                limit = form.cleaned_data.get('limit')
                area = form.cleaned_data.get('area')
                form_valid_for_api = True
                if not essay_prompt or not essay_prompt.strip(): form.add_error('essay_prompt', 'Obrigatório.'); form_valid_for_api = False
                if not form_valid_for_api: logger.warning("Tentativa Geração R. Discursiva campo obrigatório ausente."); context['error_message'] = "Erro formulário: Verifique campos obrigatórios."
                else:
                    logger.info(f"Form Gerar R. Discursiva válido API. Prompt: '{essay_prompt[:80]}...'")
                    try:
                        essay_answer = service.generate_discursive_answer(essay_prompt=essay_prompt, key_points=key_points, limit=limit, area=area)
                        logger.info("Resposta discursiva modelo gerada IA."); context['error_message'] = None
                    except (AIResponseError, AIServiceError, GeneratorError, ConfigurationError, Exception) as e:
                        logger.error(f"Erro gerar R. Discursiva: {e}", exc_info=True); context['error_message'] = f"Falha gerar resposta: {e}"
            else: logger.warning("Tentativa Geração R. Discursiva form inválido."); context['error_message'] = "Formulário inválido. Corrija erros."
    context['essay_answer'] = essay_answer
    logger.debug(f"Contexto final (generate_discursive_view): { {k: v for k, v in context.items() if k not in ['essay_answer', 'form']} }")
    return render(request, 'generator/discursive_generator.html', context)


# --- VISÃO GERAR QUESTÃO DISCURSIVA (Mantida) ---
def generate_discursive_exam_view(request):
    # ... (código como antes) ...
    context, service, service_initialized = _get_base_context_and_service()
    discursive_exam_text = None
    form = DiscursiveExamForm(request.POST or None)
    context['form'] = form
    context['error_message'] = context.get('error_message')
    if request.method == 'POST':
        if not service_initialized or not service: logger.error("POST generate_discursive_exam_view s/ serviço IA."); context['error_message'] = context.get('error_message', "Serviço IA indisponível.")
        else:
            logger.info("POST generate_discursive_exam_view")
            if form.is_valid():
                base_topic_or_context = form.cleaned_data.get('base_topic_or_context')
                num_aspects = form.cleaned_data.get('num_aspects', 3)
                area = form.cleaned_data.get('area')
                complexity = form.cleaned_data.get('complexity', 'Intermediária')
                language = form.cleaned_data.get('language', 'pt-br')
                form_valid_for_api = True
                if not base_topic_or_context or not base_topic_or_context.strip(): form.add_error('base_topic_or_context', 'Obrigatório.'); form_valid_for_api = False
                if not form_valid_for_api: logger.warning("Tentativa Geração Q. Discursiva s/ 'base_topic_or_context'."); context['error_message'] = "Erro formulário: Verifique campos obrigatórios."
                else:
                    logger.info(f"Form Gerar Q. Disc. válido API. Tópico: '{base_topic_or_context[:80]}...' Idioma: {language}")
                    try:
                        discursive_exam_text = service.generate_discursive_exam_question(base_topic_or_context=base_topic_or_context, num_aspects=num_aspects, area=area, complexity=complexity, language=language)
                        logger.info("Estrutura questão discursiva gerada IA."); context['error_message'] = None
                    except (AIResponseError, AIServiceError, GeneratorError, ParsingError, ConfigurationError, Exception) as e:
                        logger.error(f"Erro gerar Q. Discursiva: {e}", exc_info=True); context['error_message'] = f"Falha gerar questão: {e}"
            else: logger.warning("Tentativa Geração Q. Discursiva form inválido."); context['error_message'] = "Formulário inválido. Corrija erros."
    context['discursive_exam_text'] = discursive_exam_text
    logger.debug(f"Contexto final (generate_discursive_exam_view): { {k: v for k, v in context.items() if k not in ['discursive_exam_text', 'form']} }")
    return render(request, 'generator/discursive_exam_generator.html', context)


# --- VIEW PARA AVALIAR RESPOSTA DISCURSIVA (FINALMENTE CORRETA) ---
def evaluate_discursive_answer_view(request):
    """Recebe resposta discursiva e contexto, chama IA para avaliação e FAZ O PARSE do resultado via utils."""
    context, service, service_initialized = _get_base_context_and_service()
    evaluation_result_text = None; evaluation_error = None
    submitted_exam_context = None; submitted_user_answer = None
    parsed_scores = None # Inicia como None

    context['form'] = DiscursiveExamForm()
    context['error_message'] = context.get('error_message')

    # <<< PASSO 2: NENHUMA FUNÇÃO DE PARSING DEFINIDA AQUI >>>

    if request.method == 'POST':
        logger.info("POST recebido: evaluate_discursive_answer_view")
        user_answer = request.POST.get('user_answer', '').strip()
        exam_context = request.POST.get('exam_context', '').strip()
        line_count = request.POST.get('line_count', '0').strip()

        submitted_exam_context = exam_context
        submitted_user_answer = user_answer

        if not service_initialized or not service: logger.error("POST evaluate_discursive_answer_view s/ serviço IA."); evaluation_error = context.get('error_message', "Serviço IA indisponível.")
        elif not user_answer: logger.warning("Avaliação sem resposta user."); evaluation_error = "Resposta user não fornecida."
        elif not exam_context: logger.warning("Avaliação sem contexto questão."); evaluation_error = "Contexto questão não fornecido."
        else:
            logger.info(f"Dados recebidos p/ avaliação. Resp: {len(user_answer)}, Contexto: {len(exam_context)}, Linhas: {line_count}")
            try:
                logger.info(">>> CHAMANDO service.evaluate_discursive_answer <<<")
                evaluation_result_text = service.evaluate_discursive_answer(exam_context=exam_context, user_answer=user_answer, line_count=line_count)
                logger.info("Avaliação textual recebida do serviço.")
                context['error_message'] = None # Limpa erro se IA funcionou

                # --- <<< CHAMADA AO PARSING REAL (IMPORTADO) >>> ---
                if evaluation_result_text:
                    try:
                        logger.info(">>> Tentando fazer o PARSE via utils.parse_evaluation_scores <<<")
                        # <<< PASSO 3: CHAMADA À FUNÇÃO REAL ATIVA >>>
                        parsed_scores = parse_evaluation_scores(evaluation_result_text)
                        logger.info(f">>> Resultado do Parsing: {parsed_scores}")

                    except NameError:
                         logger.error("!!! FUNÇÃO 'parse_evaluation_scores' NÃO ENCONTRADA/IMPORTADA !!!")
                         evaluation_error = "Erro interno: Função de parsing não encontrada. Verifique utils.py e o import."
                         parsed_scores = None
                    except (ParsingError, ValueError, Exception) as parse_error:
                        logger.error(f"Erro durante o PARSE do resultado: {parse_error}", exc_info=True)
                        evaluation_error = f"Erro ao processar resultado: {parse_error}. Veja resultado bruto."
                        parsed_scores = None
                else:
                    logger.warning("Serviço de IA retornou texto vazio, nada para parsear.")
                    parsed_scores = None # Garante que é None se texto for vazio
                # --- <<< FIM DA CHAMADA AO PARSING >>> ---

            except (AIResponseError, AIServiceError, GeneratorError, ConfigurationError, Exception) as e:
                 logger.error(f"Erro ao chamar o serviço de avaliação discursiva: {e}", exc_info=True)
                 evaluation_error = f"Erro comunicação IA durante avaliação: {e}"
                 evaluation_result_text = None
    elif request.method == 'GET':
        logger.warning("GET evaluate_discursive_answer_view, redirecionando.")
        return redirect('generate_discursive_exam')

    # Atualiza o contexto final
    context['evaluation_result_text'] = evaluation_result_text
    context['evaluation_error'] = evaluation_error
    context['submitted_exam_context'] = submitted_exam_context
    context['submitted_user_answer'] = submitted_user_answer
    context['parsed_scores'] = parsed_scores # Passa o resultado do parsing (ou None)

    logger.debug(f"Contexto final (evaluate_discursive_answer_view): { {k: v for k, v in context.items() if k not in ['submitted_user_answer', 'submitted_exam_context', 'form', 'evaluation_result_text']} }")
    return render(request, 'generator/discursive_evaluation_result.html', context)
# --- FIM VIEW AVALIAÇÃO ---


# --- Função de Teste (Mantida) ---
def test_print_view(request):
    # ... (código como antes) ...
    message = f">>> TESTE PRINT VIEW EXECUTADO em {datetime.datetime.now()} <<<"
    print(message)
    logger.info(">>> Log INFO da test_print_view (via logger do app 'generator')")
    logger.warning(">>> Log WARNING da test_print_view")
    return HttpResponse(f"<h1>Teste Concluído</h1><p>{message}</p><p>Verifique o console/terminal onde o servidor Django está rodando para ver o print e os logs.</p>")