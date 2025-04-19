# generator/views.py (Atualizado com dashboard_view)

from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import timezone
import logging
import datetime
# import re # Não mais necessário aqui
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required # Import do decorador

# Importa Formulários
from .forms import QuestionGeneratorForm, DiscursiveAnswerForm, DiscursiveExamForm, CustomUserCreationForm
# Importa Serviço e Exceções
from .services import QuestionGenerationService
from .exceptions import ( GeneratorError, ConfigurationError, AIServiceError, AIResponseError, ParsingError )
# Importa Parser e Models
from .utils import parse_evaluation_scores
# <<< Models importados (garanta que todos necessários estão aqui) >>>
from .models import Questao, AreaConhecimento, TentativaResposta, Avaliacao
from django.http import JsonResponse # Para retornar JSON
from django.views.decorators.http import require_POST # Para garantir que só aceite POST
import json # Para decodificar o corpo da requisição JSON

logger = logging.getLogger('generator')


# --- NOVA VIEW: Validação Individual C/E (AJAX) ---
@login_required # Protege a view
@require_POST # Garante que esta view só aceite requisições POST
def validate_single_ce_view(request):
    """
    Recebe uma resposta para UM item C/E via POST (JSON/AJAX),
    valida, salva a tentativa/avaliação e retorna o resultado em JSON.
    """
    try:
        # Decodifica o corpo da requisição JSON enviado pelo JavaScript
        data = json.loads(request.body)
        questao_id = data.get('questao_id')
        user_answer = data.get('user_answer') # Espera 'C' ou 'E'

        logger.info(f"Recebido pedido AJAX validate_single_ce por {request.user.username} para Questao ID: {questao_id}")

        # Validações dos dados recebidos
        if not questao_id or user_answer not in ['C', 'E']:
            logger.warning(f"Dados inválidos recebidos: ID={questao_id}, Resposta={user_answer}")
            return JsonResponse({'error': 'Dados inválidos recebidos.'}, status=400) # Bad Request

        # Busca a Questão e realiza a validação/salvamento (similar à validate_answers_view, mas para um item)
        try:
            questao_obj = Questao.objects.get(id=questao_id, tipo='CE')

            # Cria/Atualiza TentativaResposta
            tentativa, _ = TentativaResposta.objects.update_or_create(
                usuario=request.user,
                questao=questao_obj,
                defaults={'resposta_ce': user_answer, 'data_resposta': timezone.now()}
            )
            logger.info(f"TentativaResposta ID {tentativa.id} (single) salva/atualizada.")

            # Valida e calcula score
            is_correct = (tentativa.resposta_ce == questao_obj.gabarito_ce)
            score = 1 if is_correct else -1

            # Cria/Atualiza Avaliacao
            avaliacao, _ = Avaliacao.objects.update_or_create(
                tentativa=tentativa,
                defaults={'correto_ce': is_correct, 'score_ce': score}
            )
            logger.info(f"Avaliacao (single) salva/atualizada. Correto: {is_correct}, Score: {score}.")

            # Prepara a resposta JSON
            response_data = {
                'correct': is_correct,
                'gabarito': questao_obj.gabarito_ce,
                'justification': questao_obj.justificativa_gabarito or "" # Envia string vazia se for None
            }
            return JsonResponse(response_data)

        except Questao.DoesNotExist:
            logger.error(f"Questão C/E ID {questao_id} não encontrada no DB para validação single.")
            return JsonResponse({'error': 'Questão não encontrada.'}, status=404) # Not Found
        except Exception as e:
            logger.error(f"Erro ao processar validação single para Questao ID {questao_id}: {e}", exc_info=True)
            return JsonResponse({'error': 'Erro interno ao processar a resposta.'}, status=500) # Internal Server Error

    except json.JSONDecodeError:
        logger.error("Erro ao decodificar JSON na validação single.")
        return JsonResponse({'error': 'Requisição JSON inválida.'}, status=400)
    except Exception as e:
        logger.error(f"Erro inesperado em validate_single_ce_view: {e}", exc_info=True)
        return JsonResponse({'error': 'Erro inesperado no servidor.'}, status=500)
# --- FIM NOVA VIEW ---

# --- Função Auxiliar (Mantida) ---
def _get_base_context_and_service():
    context = {}; service = None; service_initialized = True; error_message = None
    try: service = QuestionGenerationService(); logger.info(">>> Service inicializado.")
    except ConfigurationError as e: logger.critical(f">>> Falha config: {e}", exc_info=False); error_message = f"Erro config: {e}."; service_initialized = False
    except Exception as e: logger.critical(f">>> Falha inesperada init: {e}", exc_info=True); error_message = f"Erro inesperado init IA: {e}"; service_initialized = False
    context['service_initialized'] = service_initialized
    if error_message: context['error_message'] = error_message
    try: now_local = timezone.localtime(timezone.now()); context['local_time'] = now_local.strftime('%d/%m/%Y %H:%M:%S %Z')
    except Exception: context['local_time'] = "N/A"
    return context, service if service_initialized else None, service_initialized

# --- VISÃO LANDING PAGE (PÚBLICA) ---
def landing_page_view(request):
    context, _, service_initialized = _get_base_context_and_service(); context['error_message'] = context.get('error_message'); return render(request, 'generator/landing_page.html', context)

# --- VISÃO CADASTRO (PÚBLICA) ---
def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid(): user = form.save(); username = form.cleaned_data.get('username'); logger.info(f"Novo usuário: {username}"); messages.success(request, f'Conta criada para {username}! Faça login.'); return redirect('login')
        else: logger.warning(f"Cadastro falhou: {form.errors.as_json()}")
    else: form = CustomUserCreationForm()
    context = {'form': form}; return render(request, 'generator/register.html', context)

# --- VISÃO GERADOR QUESTÕES C/E (PROTEGIDA e SALVANDO QUESTÃO) ---
@login_required
def generate_questions_view(request):
    context, service, service_initialized = _get_base_context_and_service()
    saved_question_list = []
    max_q = getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 5)
    form = QuestionGeneratorForm(request.POST or None, max_questions=max_q)
    context['form'] = form
    context['error_message'] = context.get('error_message')
    if request.method == 'POST':
        if not service_initialized or not service: logger.error("POST generate_questions_view s/ serviço IA."); context['error_message'] = context.get('error_message', "Serviço IA indisponível.")
        else:
            logger.info(f"POST generate_questions_view (C/E Tópico) por {request.user.username}")
            if form.is_valid():
                topic_text = form.cleaned_data.get('topic'); num_questions = form.cleaned_data.get('num_questions'); difficulty = form.cleaned_data.get('difficulty_level'); form_valid_for_api = True
                if not topic_text or not topic_text.strip(): form.add_error('topic', 'Obrigatório.'); form_valid_for_api = False
                if num_questions is None: form.add_error('num_questions', 'Obrigatório.'); form_valid_for_api = False
                if not difficulty or not difficulty.strip(): form.add_error('difficulty_level', 'Obrigatório.'); form_valid_for_api = False
                if not form_valid_for_api: logger.warning("Geração Q C/E Tópico c/ campo obrigatório ausente."); context['error_message'] = "Erro formulário: Verifique campos obrigatórios."
                else:
                    logger.info(f"Form Q C/E válido API. Solicitando {num_questions}q [{difficulty}] TÓPICO: '{topic_text[:80]}...' (User: {request.user.username})")
                    try:
                        generated_questions_data = service.generate_questions(topic=topic_text, num_questions=num_questions, difficulty_level=difficulty)
                        if not generated_questions_data: logger.warning("Serviço Q C/E (Tópico) retornou vazio."); context['error_message'] = "IA não retornou questões válidas."
                        else:
                            logger.info(f"Questões C/E recebidas: {len(generated_questions_data)}. Salvando..."); context['error_message'] = None; saved_question_list = []
                            for item_data in generated_questions_data:
                                try:
                                    gabarito = item_data.get('gabarito')
                                    if gabarito not in ['C', 'E']: logger.warning(f"Item C/E c/ gabarito inválido '{gabarito}' não salvo."); continue
                                    q = Questao(tipo='CE', texto_comando=item_data.get('afirmacao', 'N/A'), gabarito_ce=gabarito, justificativa_gabarito=item_data.get('justificativa'), dificuldade=difficulty, criado_por=request.user); q.save(); saved_question_list.append(q)
                                except Exception as save_error: logger.error(f"Erro salvar questão C/E: {save_error}. Item: {item_data}", exc_info=True); messages.error(request, f"Erro salvar questão.")
                            logger.info(f"{len(saved_question_list)} questões C/E salvas.");
                            if len(saved_question_list) < len(generated_questions_data): messages.warning(request, f"Algumas questões geradas não foram salvas.")
                    except ParsingError as e: logger.error(f"Erro PARSING INTERNO (C/E): {e}", exc_info=True); context['error_message'] = f"Erro processar resposta IA (C/E): {e}"
                    except (AIResponseError, AIServiceError, GeneratorError, ConfigurationError, Exception) as e: logger.error(f"Erro GERAL geração Q C/E Tópico: {e}", exc_info=True); context['error_message'] = f"Falha gerar questões: {e}"
            else: logger.warning("Tentativa Geração Q C/E Tópico form inválido."); context['error_message'] = "Formulário inválido. Corrija erros."
    context['questions'] = saved_question_list
    logger.debug(f"Contexto final (generate_questions_view): User={request.user.username}, { {k: v for k, v in context.items() if k not in ['questions', 'form']} }")
    return render(request, 'generator/question_generator.html', context)


# --- VISÃO VALIDAR RESPOSTAS C/E (MODIFICADA PARA SALVAR TENTATIVA E AVALIAÇÃO) ---
@login_required
def validate_answers_view(request):
    context, _, _ = _get_base_context_and_service()
    performance_data = None; results_list = []; error_processing = None
    context['form'] = QuestionGeneratorForm(max_questions=getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 5))

    if request.method == 'POST':
        logger.info(f"POST validate_answers_view por {request.user.username}")
        try:
            all_post_keys = request.POST.keys()
            # Pega todos os índices presentes no POST que iniciam com 'questao_id_'
            indices = sorted(list(set([int(k.split('_')[-1]) for k in all_post_keys if k.startswith('questao_id_')])))
            if not indices: raise ValueError("Nenhum índice/ID de questão encontrado no POST.")

            attempt_results = [] # Guarda resultados para exibir no template
            total_processed = 0; correct_count = 0; incorrect_count = 0

            for index in indices:
                user_answer = request.POST.get(f'resposta_{index}')
                questao_id = request.POST.get(f'questao_id_{index}')

                # Validações básicas dos dados recebidos do form
                if user_answer is None or user_answer.strip().upper() not in ['C', 'E']:
                    logger.warning(f"Índice {index}: Resposta inválida/ausente ('{user_answer}'). Pulando."); continue
                if not questao_id:
                    logger.warning(f"Índice {index}: ID da questão ausente. Pulando."); continue

                try:
                    # 1. Busca a Questao original no DB
                    questao_obj = Questao.objects.get(id=questao_id, tipo='CE')

                    # 2. Cria e salva a TentativaResposta
                    tentativa, created_tentativa = TentativaResposta.objects.update_or_create(
                        usuario=request.user,
                        questao=questao_obj,
                        # Evita duplicatas se o usuário reenviar o form, atualiza a resposta
                        defaults={'resposta_ce': user_answer.strip().upper(), 'data_resposta': timezone.now()}
                    )
                    log_msg_tentativa = "criada" if created_tentativa else "atualizada"
                    logger.info(f"TentativaResposta ID {tentativa.id} {log_msg_tentativa} para Questao ID {questao_id}.")

                    # 3. Valida a resposta e calcula score
                    is_correct = (tentativa.resposta_ce == questao_obj.gabarito_ce)
                    score = 1 if is_correct else -1 # Ou 0 se preferir não penalizar erro

                    # 4. Cria ou atualiza a Avaliacao
                    avaliacao, created_avaliacao = Avaliacao.objects.update_or_create(
                        tentativa=tentativa, # Chave de busca (OneToOne)
                        defaults={'correto_ce': is_correct, 'score_ce': score} # Dados a salvar/atualizar
                    )
                    log_msg_avaliacao = "criada" if created_avaliacao else "atualizada"
                    logger.info(f"Avaliacao {log_msg_avaliacao} para Tentativa ID {tentativa.id}. Correto: {is_correct}, Score: {score}.")

                    # 5. Prepara dados para exibir no template
                    attempt_results.append({
                        'index': index, # Pode ser útil para referência
                        'afirmacao': questao_obj.texto_comando,
                        'user_answer': tentativa.resposta_ce,
                        'gabarito': questao_obj.gabarito_ce,
                        'correct': avaliacao.correto_ce,
                        'justificativa': questao_obj.justificativa_gabarito or "Não fornecida."
                    })

                    # Atualiza contadores
                    total_processed += 1
                    if is_correct: correct_count += 1
                    else: incorrect_count += 1

                except Questao.DoesNotExist:
                    logger.error(f"Questão C/E ID {questao_id} (Índice {index}) não encontrada. Pulando.")
                    error_processing = (error_processing or "") + f" Erro: Questão {index+1} não encontrada."
                except Exception as db_error:
                    logger.error(f"Erro DB ao processar item {index} (Questao ID {questao_id}): {db_error}", exc_info=True)
                    error_processing = (error_processing or "") + f" Erro ao salvar item {index+1}."

            # Prepara resultados finais
            results_list = attempt_results
            if not results_list and not error_processing: # Se a lista for vazia E não houve erro antes
                 error_processing = "Nenhum item válido processado."

            if total_processed > 0: # Calcula performance apenas se algo foi processado
                 final_score = correct_count - incorrect_count
                 percentage_correct = round((correct_count / total_processed) * 100)
                 performance_data = {
                     'correct': correct_count, 'incorrect': incorrect_count,
                     'total': total_processed, 'score': final_score, 'percentage': percentage_correct
                 }
                 logger.info(f"Performance User {request.user.username} (Salvo): Score {final_score}/{total_processed}.")

        except ValueError as e: logger.error(f"Erro ValueError validate: {e}", exc_info=True); error_processing = f"Erro dados POST: {e}."
        except Exception as e: logger.exception(f"Erro Exception validate: {e}"); error_processing = "Erro inesperado processamento."

        context['results'] = results_list
        if performance_data: context['performance'] = performance_data
        if error_processing: context['error_message'] = error_processing
        logger.debug(f"Contexto final (validate_answers_view): User={request.user.username}, { {k: v for k, v in context.items() if k not in ['results', 'performance', 'form']} }")
        return render(request, 'generator/question_generator.html', context)

    elif request.method == 'GET': return redirect('landing_page')
    context['error_message'] = context.get('error_message', "Acesso inválido.")
    return render(request, 'generator/question_generator.html', context)


# --- VISÃO GERAR RESPOSTA DISCURSIVA (Mantida) ---
@login_required
def generate_discursive_view(request):
    # ... (código como antes) ...
    context, service, service_initialized = _get_base_context_and_service(); essay_answer = None; form = DiscursiveAnswerForm(request.POST or None); context['form'] = form; context['error_message'] = context.get('error_message')
    if request.method == 'POST':
        if not service_initialized or not service: logger.error("POST generate_discursive_view s/ serviço IA."); context['error_message'] = context.get('error_message', "Serviço IA indisponível.")
        else:
            logger.info(f"POST generate_discursive_view por {request.user.username}")
            if form.is_valid():
                essay_prompt = form.cleaned_data.get('essay_prompt'); key_points = form.cleaned_data.get('key_points'); limit = form.cleaned_data.get('limit'); area = form.cleaned_data.get('area'); form_valid_for_api = True
                if not essay_prompt or not essay_prompt.strip(): form.add_error('essay_prompt', 'Obrigatório.'); form_valid_for_api = False
                if not form_valid_for_api: logger.warning("Tentativa Geração R. Discursiva campo obrigatório ausente."); context['error_message'] = "Erro formulário: Verifique campos obrigatórios."
                else:
                    logger.info(f"Form Gerar R. Discursiva válido API. Prompt: '{essay_prompt[:80]}...' (User: {request.user.username})")
                    try: essay_answer = service.generate_discursive_answer(essay_prompt=essay_prompt, key_points=key_points, limit=limit, area=area); logger.info("Resposta discursiva modelo gerada IA."); context['error_message'] = None
                    except (AIResponseError, AIServiceError, GeneratorError, ConfigurationError, Exception) as e: logger.error(f"Erro gerar R. Discursiva: {e}", exc_info=True); context['error_message'] = f"Falha gerar resposta: {e}"
            else: logger.warning("Tentativa Geração R. Discursiva form inválido."); context['error_message'] = "Formulário inválido. Corrija erros."
    context['essay_answer'] = essay_answer
    logger.debug(f"Contexto final (generate_discursive_view): User={request.user.username}, { {k: v for k, v in context.items() if k not in ['essay_answer', 'form']} }")
    return render(request, 'generator/discursive_generator.html', context)


# --- VISÃO GERAR QUESTÃO DISCURSIVA (Mantida - já salva no DB) ---
@login_required
def generate_discursive_exam_view(request):
    # ... (código como antes, já salva Questao) ...
    context, service, service_initialized = _get_base_context_and_service(); discursive_exam_text = None; questao_id = None; form = DiscursiveExamForm(request.POST or None); context['form'] = form; context['error_message'] = context.get('error_message')
    if request.method == 'POST':
        if not service_initialized or not service: logger.error("POST generate_discursive_exam_view s/ serviço IA."); context['error_message'] = context.get('error_message', "Serviço IA indisponível.")
        else:
            logger.info(f"POST generate_discursive_exam_view por {request.user.username}")
            if form.is_valid():
                base_topic_or_context = form.cleaned_data.get('base_topic_or_context'); num_aspects = form.cleaned_data.get('num_aspects', 3); area_nome = form.cleaned_data.get('area'); complexity = form.cleaned_data.get('complexity', 'Intermediária'); language = form.cleaned_data.get('language', 'pt-br'); form_valid_for_api = True
                if not base_topic_or_context or not base_topic_or_context.strip(): form.add_error('base_topic_or_context', 'Obrigatório.'); form_valid_for_api = False
                if not form_valid_for_api: logger.warning("Tentativa Geração Q. Discursiva s/ 'base_topic_or_context'."); context['error_message'] = "Erro formulário: Verifique campos obrigatórios."
                else:
                    logger.info(f"Form Gerar Q. Disc. válido API. Tópico: '{base_topic_or_context[:80]}...' Idioma: {language} (User: {request.user.username})")
                    try:
                        discursive_exam_text = service.generate_discursive_exam_question(base_topic_or_context=base_topic_or_context, num_aspects=num_aspects, area=area_nome, complexity=complexity, language=language)
                        logger.info("Estrutura questão discursiva recebida da IA."); context['error_message'] = None
                        if discursive_exam_text:
                            area_obj = None
                            if area_nome:
                                try: area_obj, created = AreaConhecimento.objects.get_or_create(nome=area_nome); logger.info(f"AreaConhecimento {'criada' if created else 'encontrada'}: {area_nome}")
                                except Exception as e_area: logger.error(f"Erro buscar/criar Area '{area_nome}': {e_area}")
                            questao_obj = Questao(tipo='DISC', texto_comando=discursive_exam_text, aspectos_discursiva=f"Abordar {num_aspects} aspectos.", dificuldade=complexity, area=area_obj, criado_por=request.user)
                            questao_obj.save(); questao_id = questao_obj.id
                            logger.info(f"Questão Discursiva ID {questao_id} salva no DB.")
                    except (AIResponseError, AIServiceError, GeneratorError, ParsingError, ConfigurationError, Exception) as e: logger.error(f"Erro gerar Q. Discursiva: {e}", exc_info=True); context['error_message'] = f"Falha gerar questão: {e}"; discursive_exam_text = None; questao_id = None
            else: logger.warning("Tentativa Geração Q. Discursiva form inválido."); context['error_message'] = "Formulário inválido. Corrija erros."
    context['discursive_exam_text'] = discursive_exam_text; context['questao_id'] = questao_id
    logger.debug(f"Contexto final (generate_discursive_exam_view): User={request.user.username}, QuestaoID={questao_id}, { {k: v for k, v in context.items() if k not in ['discursive_exam_text', 'form', 'questao_id']} }")
    return render(request, 'generator/discursive_exam_generator.html', context)


# --- VIEW PARA AVALIAR RESPOSTA DISCURSIVA (MODIFICADA PARA SALVAR TENTATIVA E AVALIAÇÃO) ---
@login_required
def evaluate_discursive_answer_view(request):
    context, service, service_initialized = _get_base_context_and_service()
    evaluation_result_text = None; evaluation_error = None
    submitted_exam_context = None; submitted_user_answer = None
    parsed_scores = None; tentativa = None # Adiciona tentativa

    context['form'] = DiscursiveExamForm() # Para reexibir página base se necessário
    context['error_message'] = context.get('error_message')

    if request.method == 'POST':
        logger.info(f"POST evaluate_discursive_answer_view por {request.user.username}")
        user_answer = request.POST.get('user_answer', '').strip()
        exam_context = request.POST.get('exam_context', '').strip() # Contexto da questão (texto bruto)
        line_count = request.POST.get('line_count', '0').strip()
        questao_id = request.POST.get('questao_id') # <<< Pega o ID da questão do form

        submitted_exam_context = exam_context; submitted_user_answer = user_answer

        # Validações Iniciais
        questao_obj = None
        if not service_initialized or not service:
             logger.error("POST evaluate_discursive_answer_view s/ serviço IA."); evaluation_error = context.get('error_message', "Serviço IA indisponível.")
        elif not user_answer:
             logger.warning("Avaliação sem resposta user."); evaluation_error = "Resposta user não fornecida."
        elif not questao_id: # Verifica se o ID veio
             logger.error("ID da questão não recebido no POST para avaliação.")
             evaluation_error = "Erro: ID da questão original não encontrado."
        else:
            try:
                # Busca a Questão original no DB
                questao_obj = Questao.objects.get(id=questao_id, tipo='DISC') # Garante que é discursiva
                logger.info(f"Questão ID {questao_id} encontrada para avaliação.")

                # --- Cria ou Atualiza a Tentativa de Resposta ---
                # Usar update_or_create para caso o usuário reenvie a mesma avaliação
                tentativa, created_tentativa = TentativaResposta.objects.update_or_create(
                    usuario=request.user,
                    questao=questao_obj,
                    # Se achar uma combinação user/questao, atualiza. Senão, cria.
                    defaults={'resposta_discursiva': user_answer, 'data_resposta': timezone.now()}
                )
                log_msg_tentativa = "criada" if created_tentativa else "atualizada"
                logger.info(f"TentativaResposta ID {tentativa.id} {log_msg_tentativa} para Questao ID {questao_id}.")

                # Agora chama a IA para avaliar
                logger.info(f"Dados enviados p/ IA: Contexto={len(exam_context)}, Resp={len(user_answer)}, Linhas={line_count}")
                try:
                    logger.info(">>> CHAMANDO service.evaluate_discursive_answer <<<")
                    evaluation_result_text = service.evaluate_discursive_answer(
                        exam_context=exam_context, # Passa o texto do comando/contexto
                        user_answer=user_answer,
                        line_count=line_count
                    )
                    logger.info("Avaliação textual recebida do serviço.")
                    context['error_message'] = None

                    # --- Tenta fazer o PARSE e Salvar/Atualizar Avaliação ---
                    if evaluation_result_text:
                        try:
                            logger.info(">>> Tentando PARSE via utils.parse_evaluation_scores <<<")
                            parsed_scores = parse_evaluation_scores(evaluation_result_text) # Chama parser externo
                            logger.info(f">>> Resultado Parsing: {parsed_scores}")

                            # --- Salva/Atualiza a Avaliação ---
                            avaliacao_obj, created_avaliacao = Avaliacao.objects.update_or_create(
                                tentativa=tentativa, # Chave primária ou link
                                defaults={ # Campos a serem atualizados ou criados
                                    'nc': parsed_scores.get('NC'), # Pega valor do dict, ou None
                                    'ne': parsed_scores.get('NE'),
                                    'npd': parsed_scores.get('NPD'),
                                    'feedback_ai': evaluation_result_text, # Texto bruto completo
                                    'justificativa_nc_ai': parsed_scores.get('Justificativa'), # Pode ser None
                                    'comentarios_ai': parsed_scores.get('Comentários'), # Pode ser None
                                    # data_avaliacao é auto_now_add, definido na criação e não atualizado aqui
                                }
                            )
                            log_msg_avaliacao = "criada" if created_avaliacao else "atualizada"
                            logger.info(f"Avaliacao {log_msg_avaliacao} no DB para Tentativa ID {tentativa.id}.")
                            # --- Fim Salvamento Avaliação ---

                        except NameError:
                             logger.error("!!! FUNÇÃO 'parse_evaluation_scores' NÃO ENCONTRADA !!!")
                             evaluation_error = "Erro interno: Função de parsing não encontrada."; parsed_scores = None
                        except (ParsingError, ValueError, TypeError, Exception) as parse_error: # Pega erros de conversão também
                            logger.error(f"Erro PARSE/SAVE Avaliação: {parse_error}", exc_info=True)
                            evaluation_error = f"Erro processar/salvar resultado: {parse_error}."; parsed_scores = None
                            # Não salva Avaliacao se o parse falhar. Tentativa já foi salva.
                    else: # evaluation_result_text vazio
                        logger.warning("Serviço IA retornou texto vazio, nada para parsear/salvar.")
                        parsed_scores = None
                # Fim do try da chamada da IA/Parsing/Save
                except (AIResponseError, AIServiceError, GeneratorError, ConfigurationError, Exception) as service_error:
                     logger.error(f"Erro chamar serviço avaliação: {service_error}", exc_info=True)
                     evaluation_error = f"Erro comunicação IA: {service_error}"; evaluation_result_text = None; parsed_scores = None
            # Fim do try de buscar questão
            except Questao.DoesNotExist:
                 logger.error(f"Questão DISC ID {questao_id} não encontrada no DB para avaliação.")
                 evaluation_error = "Erro: Questão original não encontrada ou inválida."
            except Exception as general_error: # Pega outros erros inesperados
                 logger.error(f"Erro inesperado em evaluate_discursive_answer_view: {general_error}", exc_info=True)
                 evaluation_error = "Ocorreu um erro inesperado no servidor."

    # Fim do if request.method == 'POST'
    elif request.method == 'GET':
        return redirect('generate_discursive_exam')

    # Atualiza contexto final ANTES de renderizar
    context['evaluation_result_text'] = evaluation_result_text
    context['evaluation_error'] = evaluation_error
    context['submitted_exam_context'] = submitted_exam_context
    context['submitted_user_answer'] = submitted_user_answer
    context['parsed_scores'] = parsed_scores
    context['tentativa_id'] = tentativa.id if tentativa else None

    logger.debug(f"Contexto final (evaluate_discursive_answer_view): User={request.user.username}, TentativaID={context['tentativa_id']}, { {k: v for k, v in context.items() if k not in ['submitted_user_answer', 'submitted_exam_context', 'form', 'evaluation_result_text']} }")
    return render(request, 'generator/discursive_evaluation_result.html', context)


# --- VIEW DASHBOARD (Mantida - já busca dados) ---
@login_required
def dashboard_view(request):
    # ... (código como antes) ...
    context, _, _ = _get_base_context_and_service(); tentativas = []; stats = {}
    try:
        tentativas = TentativaResposta.objects.filter(usuario=request.user).select_related('questao', 'questao__area').prefetch_related('avaliacao').order_by('-data_resposta')
        logger.info(f"Buscando histórico {request.user.username}. Encontradas {tentativas.count()} tentativas.")
        total_ce = 0; acertos_ce = 0; erros_ce = 0
        for t in tentativas:
            if t.questao.tipo == 'CE':
                total_ce += 1
                try: avaliacao = getattr(t, 'avaliacao', None)
                except Avaliacao.DoesNotExist: avaliacao = None # Segurança extra
                if avaliacao and avaliacao.correto_ce is not None:
                    if avaliacao.correto_ce: acertos_ce += 1
                    else: erros_ce += 1
        score_ce = acertos_ce - erros_ce
        percentual_ce = round((acertos_ce / total_ce) * 100) if total_ce > 0 else 0
        stats = {'total_geral': tentativas.count(), 'total_ce': total_ce, 'acertos_ce': acertos_ce, 'erros_ce': erros_ce, 'score_ce': score_ce, 'percentual_ce': percentual_ce}
        logger.info(f"Stats C/E {request.user.username}: {stats}")
    except Exception as e: logger.error(f"Erro buscar/calcular dashboard {request.user.username}: {e}", exc_info=True); messages.error(request, "Erro carregar desempenho."); tentativas = []; stats = {}
    context['tentativas_list'] = tentativas[:20]; context['stats'] = stats
    return render(request, 'generator/dashboard.html', context)


# --- Função de Teste (Mantida) ---
@login_required
def test_print_view(request):
    # ... (código como antes) ...
    message = f">>> TESTE PRINT VIEW EXECUTADO por {request.user.username} em {datetime.datetime.now()} <<<"; print(message); logger.info(f">>> Log INFO test_print_view (User: {request.user.username})"); logger.warning(">>> Log WARNING test_print_view"); return HttpResponse(f"<h1>Teste Concluído</h1><p>{message}</p><p>Logado como: {request.user.username}</p>")