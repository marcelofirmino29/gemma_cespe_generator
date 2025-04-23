# generator/views.py 

from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import timezone
import logging
import datetime
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required # Import do decorador
from datetime import datetime # Garanta que datetime está importado
#from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# Importa Formulários
from .forms import QuestionGeneratorForm, DiscursiveAnswerForm, DiscursiveExamForm, CustomUserCreationForm
# Importa Serviço e Exceções
from .services import QuestionGenerationService
from .exceptions import ( GeneratorError, ConfigurationError, AIServiceError, AIResponseError, ParsingError )
# Importa Parser e Models
from .utils import parse_evaluation_scores
from .models import Questao, AreaConhecimento, TentativaResposta, Avaliacao
from django.http import JsonResponse # Para retornar JSON
from django.views.decorators.http import require_POST # Para garantir que só aceite POST
#from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import json # Para decodificar o corpo da requisição JSON

from .forms import SimuladoConfigForm
from django.db.models import Q

logger = logging.getLogger('generator')

# --- Validação Individual C/E (AJAX) ---
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
# --- FIM DA VIEW ---

# --- Função Auxiliar ---
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

# --- VISÃO DASHBOARD (PROTEGIDA) ---
@login_required
def generate_questions_view(request):
    context, service, service_initialized = _get_base_context_and_service()
    context['questions'] = None # Lista de questões ou None
    context['main_motivador'] = None
    context['error_message'] = context.get('error_message')

    # Cria um formulário (será usado em GET e POST)
    max_q = getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 150)
    form = QuestionGeneratorForm(request.POST or None, max_questions=max_q)
    context['form'] = form

    # --- Lógica POST (Gera, Salva, Guarda IDs na Sessão e Redireciona) ---
    if request.method == 'POST' and service_initialized and service:
        logger.info(f"POST generate_questions_view por {request.user.username}")
        if form.is_valid():
            topic_text = form.cleaned_data.get('topic'); num_questions = form.cleaned_data.get('num_questions'); difficulty = form.cleaned_data.get('difficulty_level'); area_obj = form.cleaned_data.get('area')
            logger.info(f"Form válido. Gerando {num_questions}q...")
            try:
                main_motivador, generated_items_data = service.generate_questions(topic=topic_text, num_questions=num_questions, difficulty_level=difficulty)
                if not generated_items_data or not isinstance(generated_items_data, list):
                    logger.warning("IA retornou dados inválidos."); context['error_message'] = "IA retornou dados em formato inesperado."; generated_items_data = []
                else: context['error_message'] = None

                saved_question_ids = []
                if generated_items_data: # Salva apenas se a lista não estiver vazia
                    logger.info(f"Itens C/E recebidos: {len(generated_items_data)}. Salvando...")
                    # ... (busca area_obj se necessário, como antes) ...
                    if area_obj is None and form.cleaned_data.get('area'): # Refetch area if needed
                       try: area_obj = AreaConhecimento.objects.get(id=form.cleaned_data.get('area').id)
                       except Exception: area_obj = None

                    for item_data in generated_items_data:
                        try:
                            if not isinstance(item_data, dict): continue
                            gabarito = item_data.get('gabarito'); assert gabarito in ['C', 'E']
                            q = Questao(tipo='CE', texto_motivador=main_motivador, texto_comando=item_data.get('afirmacao'), gabarito_ce=gabarito, justificativa_gabarito=item_data.get('justificativa'), dificuldade=(difficulty or 'medio'), area=area_obj, criado_por=request.user); q.save(); saved_question_ids.append(q.id)
                        except Exception as save_error: logger.error(f"Erro salvar questão C/E: {save_error}", exc_info=True)

                    logger.info(f"{len(saved_question_ids)} questões C/E salvas no DB.")
                    if saved_question_ids:
                        messages.success(request, f"{len(saved_question_ids)} questões C/E geradas e salvas!")
                        # <<< GUARDA OS IDs DAS QUESTÕES RECÉM-SALVAS NA SESSÃO >>>
                        request.session['latest_ce_ids'] = saved_question_ids
                        request.session['latest_ce_motivador'] = main_motivador # Guarda motivador também
                    else:
                         messages.warning(request,"Nenhuma questão válida pôde ser salva.")
                    if len(saved_question_ids) < len(generated_items_data): messages.warning(request,"Alguns itens podem não ter sido salvos.")
                # <<< Redireciona para GET após processar o POST >>>
                return redirect('generator:generate_questions')

            except (ParsingError, AIResponseError, AIServiceError, GeneratorError, ConfigurationError, Exception) as e:
                logger.error(f"Erro GERAL Geração C/E: {e}", exc_info=True); context['error_message'] = f"Falha gerar/processar: {e}"
                # Renderiza o form com o erro, sem questões
                return render(request, 'generator/question_generator.html', context)
        else: # Form POST inválido
             logger.warning(f"Form Geração C/E inválido: {form.errors.as_json()}")
             # Renderiza o form com os erros, sem questões
             return render(request, 'generator/question_generator.html', context)

    # --- Lógica GET (Verifica Sessão para exibir APENAS o último lote) ---
    else: # request.method == 'GET'
        logger.debug(f"GET generate_questions_view por {request.user.username}")
        # Tenta pegar os IDs da última geração da sessão
        latest_ids = request.session.pop('latest_ce_ids', None) # .pop() pega e remove
        latest_motivador = request.session.pop('latest_ce_motivador', None) # Pega motivador

        if latest_ids:
            logger.info(f"Exibindo último lote de questões C/E geradas (IDs: {latest_ids})")
            # Busca APENAS as questões recém-criadas
            question_list = Questao.objects.filter(id__in=latest_ids).order_by('id') # Mantém ordem de geração? Ou -criado_em?
            context['questions'] = question_list # Passa a LISTA, não um Page Object
            context['main_motivador'] = latest_motivador
        else:
            # Se não tem 'latest_ce_ids' na sessão, não busca nada
            logger.debug("Nenhum lote recente na sessão, exibindo apenas o formulário.")
            context['questions'] = None
            context['main_motivador'] = None

        # Renderiza o template. 'questions' será a lista do último lote ou None.
        return render(request, 'generator/question_generator.html', context)
    
# --- VISÃO VALIDAR RESPOSTAS C/E ---
@login_required
def validate_answers_view(request):
    # ... (código como antes) ...
     context, _, _ = _get_base_context_and_service(); performance_data = None; results_list = []; error_processing = None; context['form'] = QuestionGeneratorForm(max_questions=getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 150))
     if request.method == 'POST':
         logger.info(f"POST validate_answers_view por {request.user.username}")
         try:
             all_post_keys = request.POST.keys(); indices_str = sorted(list(set([k.split('_')[-1] for k in all_post_keys if k.startswith('questao_id_')])))
             if not indices_str: raise ValueError("Nenhum ID questão POST.")
             indices = [int(i) for i in indices_str]; attempt_results = []; total_processed = 0; correct_count = 0; incorrect_count = 0
             for index in indices:
                 user_answer = request.POST.get(f'resposta_{index}'); questao_id = request.POST.get(f'questao_id_{index}') # <<< Cuidado: nome do radio no template pode ter mudado para resposta_qX
                 if user_answer is None: user_answer = request.POST.get(f'resposta_q{questao_id}') # Tenta pegar pelo nome alternativo se o JS estiver ativo
                 if user_answer is None or user_answer.strip().upper() not in ['C', 'E']: logger.warning(f"Idx {index}/QID {questao_id}: Resp. inválida. Pulando."); continue
                 if not questao_id: logger.warning(f"Idx {index}: ID ausente. Pulando."); continue
                 try:
                     questao_obj = Questao.objects.get(id=questao_id, tipo='CE')
                     tentativa, _ = TentativaResposta.objects.update_or_create(usuario=request.user, questao=questao_obj, defaults={'resposta_ce': user_answer.strip().upper(), 'data_resposta': timezone.now()})
                     is_correct = (tentativa.resposta_ce == questao_obj.gabarito_ce); score = 1 if is_correct else -1
                     avaliacao, _ = Avaliacao.objects.update_or_create(tentativa=tentativa, defaults={'correto_ce': is_correct, 'score_ce': score})
                     logger.info(f"Avaliacao C/E salva p/ Tentativa {tentativa.id}. Correto: {is_correct}")
                     attempt_results.append({'index': index, 'afirmacao': questao_obj.texto_comando, 'user_answer': tentativa.resposta_ce, 'gabarito': questao_obj.gabarito_ce, 'correct': avaliacao.correto_ce, 'justificativa': questao_obj.justificativa_gabarito}) # Passa direto (pode ser None)
                     total_processed += 1;
                     if is_correct: correct_count += 1
                     else: incorrect_count += 1
                 except Questao.DoesNotExist: logger.error(f"Questão C/E ID {questao_id} não encontrada. Pulando."); error_processing = (error_processing or "") + f" Erro: Questão {index+1} não encontrada."
                 except Exception as db_error: logger.error(f"Erro DB item {index} (Q ID {questao_id}): {db_error}", exc_info=True); error_processing = (error_processing or "") + f" Erro salvar item {index+1}."
             results_list = attempt_results
             if not results_list and not error_processing: error_processing = "Nenhum item válido processado."
             if total_processed > 0:
                  final_score = correct_count - incorrect_count; percentage_correct = round((correct_count / total_processed) * 100)
                  performance_data = {'correct': correct_count, 'incorrect': incorrect_count, 'total': total_processed, 'score': final_score, 'percentage': percentage_correct }
                  logger.info(f"Performance User {request.user.username} (Salvo): Score {final_score}/{total_processed}.")
         except ValueError as e: logger.error(f"Erro ValueError validate: {e}"); error_processing = f"Erro dados POST: {e}."
         except Exception as e: logger.exception(f"Erro Exception validate: {e}"); error_processing = "Erro inesperado."
         context['results'] = results_list; context['performance'] = performance_data; context['error_message'] = error_processing
         logger.debug(f"Contexto final (validate_answers_view): User={request.user.username}, ...")
         return render(request, 'generator/question_generator.html', context)
     elif request.method == 'GET': return redirect('generator:landing_page')
     context['error_message'] = context.get('error_message', "Acesso inválido.")
     return render(request, 'generator/question_generator.html', context)

# --- VISÃO VALIDAR RESPOSTAS C/E (SALVA TENTATIVA E AVALIAÇÃO) ---
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

    elif request.method == 'GET': return redirect('generator:landing_page')
    context['error_message'] = context.get('error_message', "Acesso inválido.")
    return render(request, 'generator/question_generator.html', context)

# --- VISÃO GERAR RESPOSTA DISCURSIVA ---
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

# --- VISÃO GERAR QUESTÃO DISCURSIVA ---
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

# --- VISÃO Configuração do Simulado (COM FILTRO DE TÓPICO) ---
@login_required
def configurar_simulado_view(request):
    context, _, _ = _get_base_context_and_service()
    form = SimuladoConfigForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            num_ce = form.cleaned_data.get('num_ce')
            area_obj = form.cleaned_data.get('area')
            dificuldade_ce = form.cleaned_data.get('dificuldade_ce')
            topico_filtro = form.cleaned_data.get('topico')

            logger.info(f"Configurando simulado C/E para {request.user.username}: "
                        f"Num={num_ce}, Area='{area_obj.nome if area_obj else 'Todas'}', "
                        f"Dif='{dificuldade_ce or 'Qualquer'}', Tópico='{topico_filtro or 'Qualquer'}'")

            selected_ids = []
            try:
                # Filtros base C/E
                ce_queryset = Questao.objects.filter(tipo='CE')
                if area_obj:
                    ce_queryset = ce_queryset.filter(area=area_obj)
                if dificuldade_ce:
                    ce_queryset = ce_queryset.filter(dificuldade=dificuldade_ce)

                if topico_filtro:
                    ce_queryset = ce_queryset.filter(
                        Q(topico__nome__icontains=topico_filtro) | Q(texto_comando__icontains=topico_filtro)
                    )
                    logger.info(f"Filtrando por tópico OU texto da questão contendo: '{topico_filtro}'")

                selected_ids = list(ce_queryset.order_by('?').values_list('id', flat=True)[:num_ce])

                if len(selected_ids) < num_ce:
                    messages.warning(request, f"Aviso: Apenas {len(selected_ids)} questões C/E encontradas com os critérios.")
                if not selected_ids:
                    messages.error(request, "Nenhuma questão C/E encontrada com os critérios selecionados.")
                    context['form'] = form
                    return render(request, 'generator/configurar_simulado.html', context)

                # Armazena na sessão (salvando os IDs, não os objetos)
                request.session['simulado_config'] = {
                    'num_ce': num_ce,
                    'area_id': area_obj.id if area_obj else None, # Salva o ID da área
                    'dificuldade_ce': dificuldade_ce,
                    'topico_filtro': topico_filtro,
                }
                request.session['simulado_questao_ids'] = selected_ids
                request.session['simulado_indice_atual'] = 0
                request.session['simulado_respostas'] = {}
                logger.info(f"Simulado C/E configurado. Questões: {len(selected_ids)}. Redirecionando...")
                messages.success(request, f"Simulado com {len(selected_ids)} questões C/E configurado!")
                return redirect('generator:realizar_simulado')

            except Exception as e:
                logger.error(f"Erro ao selecionar questões C/E: {e}", exc_info=True)
                messages.error(request, "Erro ao preparar simulado.")
                context['form'] = form
        else:
            logger.warning(f"Form config simulado inválido: {form.errors.as_json()}")

    context['form'] = form
    return render(request, 'generator/configurar_simulado.html', context)

# --- VIEW Realização do Simulado (LÓGICA DE ÍNDICE CORRIGIDA) ---
@login_required
def realizar_simulado_view(request):
    context, _, _ = _get_base_context_and_service()
    questao_ids = request.session.get('simulado_questao_ids', [])
    # Índice da questão a ser exibida/processada AGORA (começa em 0)
    indice_atual = request.session.get('simulado_indice_atual', 0) # Default 0

    # --- Lógica para POST ---
    if request.method == 'POST':
        resposta_submetida = request.POST.get('resposta_simulado')
        questao_id_respondida = request.POST.get('questao_id')

        if not questao_id_respondida or resposta_submetida is None: # Verifica ambos
            messages.warning(request, "Resposta ou ID da questão ausente.")
            return redirect('generator:realizar_simulado') # Recarrega questão atual

        try:
            questao_obj = Questao.objects.get(id=questao_id_respondida)
            # Verifica se o ID da questão submetida corresponde ao esperado pelo índice atual
            if questao_ids[indice_atual] != questao_obj.id:
                 messages.error(request, "Erro de sequência no simulado. Reiniciando configuração.")
                 request.session.pop('simulado_questao_ids', None); request.session.pop('simulado_indice_atual', None)
                 return redirect('generator:configurar_simulado')

            # Salva/Atualiza TentativaResposta
            defaults_tentativa = {'data_resposta': timezone.now()}
            if questao_obj.tipo == 'CE':
                resposta_ce_valida = resposta_submetida.strip().upper()
                if resposta_ce_valida in ['C', 'E']: defaults_tentativa['resposta_ce'] = resposta_ce_valida
                else: messages.error(request, "Resposta C/E inválida."); return redirect('generator:realizar_simulado')
            # Removido Bloco DISC aqui pois simulado é só C/E
            # elif questao_obj.tipo == 'DISC': defaults_tentativa['resposta_discursiva'] = resposta_submetida.strip()
            else: messages.error(request,"Tipo questão inválido."); return redirect('generator:configurar_simulado')

            tentativa, _ = TentativaResposta.objects.update_or_create(usuario=request.user, questao=questao_obj, defaults=defaults_tentativa)
            logger.info(f"Tentativa ID {tentativa.id} salva/atualizada p/ Q ID {questao_id_respondida}.")

            # Salva/Atualiza Avaliação C/E
            if questao_obj.tipo == 'CE':
                is_correct = (tentativa.resposta_ce == questao_obj.gabarito_ce); score = 1 if is_correct else -1
                avaliacao, _ = Avaliacao.objects.update_or_create(tentativa=tentativa, defaults={'correto_ce': is_correct, 'score_ce': score})
                logger.info(f"Avaliacao C/E salva/atualizada p/ Tentativa ID {tentativa.id}.")

            # <<< CORREÇÃO: Incrementa o índice ATUAL da sessão >>>
            indice_proxima = indice_atual + 1
            request.session['simulado_indice_atual'] = indice_proxima
            logger.info(f"Usuário {request.user.username} respondeu índice {indice_atual}, avançando para {indice_proxima}.")

        except Questao.DoesNotExist: messages.error(request,...); return redirect('generator:configurar_simulado')
        except IndexError: messages.error(request, "Erro: Tentativa de acessar índice inválido."); return redirect('generator:configurar_simulado')
        except Exception as e: logger.error(f"Erro salvar tentativa simulado: {e}", exc_info=True); messages.error(request, "Erro ao salvar resposta."); return redirect('realizar_simulado')

        # Redireciona para si mesmo (GET) para carregar a próxima questão ou finalizar
        return redirect('generator:realizar_simulado')

    # --- Lógica para GET ---
    if not questao_ids: messages.warning(request, "Simulado não iniciado."); return redirect('generator:configurar_simulado')

    # Verifica se o índice atual já ultrapassou a lista de questões
    if indice_atual >= len(questao_ids):
        messages.success(request, "Simulado concluído!")
        simulado_finalizado_ids = request.session.pop('simulado_questao_ids', [])
        request.session['finalizado_simulado_questao_ids'] = simulado_finalizado_ids # Guarda para resultado
        request.session.pop('simulado_indice_atual', None)
        request.session.pop('simulado_respostas', None)
        request.session.pop('simulado_config', None)
        logger.info(f"Simulado finalizado para {request.user.username}. IDs: {simulado_finalizado_ids}")
        return redirect('generator:resultado_simulado') # Redireciona para a página de resultado

    # Busca a questão do índice atual para exibir
    questao_id_atual = questao_ids[indice_atual]
    try:
        questao_atual = Questao.objects.select_related('area').get(id=questao_id_atual)
        context['questao'] = questao_atual
        context['indice_atual'] = indice_atual + 1 # Para exibição (1 de N)
        context['total_questoes'] = len(questao_ids)
        logger.info(f"Exibindo questão índice {indice_atual} (ID: {questao_id_atual}) para {request.user.username}.")
    except Questao.DoesNotExist: messages.error(request,...); request.session.pop('simulado_questao_ids', None); return redirect('generator:configurar_simulado')
    except Exception as e: logger.error(f"Erro buscar questão {questao_id_atual}: {e}", exc_info=True); messages.error(request, "Erro carregar questão."); return redirect('configurar_simulado')

    return render(request, 'generator/realizar_simulado.html', context)

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
        return redirect('generator:generate_discursive_exam')

    # Atualiza contexto final ANTES de renderizar
    context['evaluation_result_text'] = evaluation_result_text
    context['evaluation_error'] = evaluation_error
    context['submitted_exam_context'] = submitted_exam_context
    context['submitted_user_answer'] = submitted_user_answer
    context['parsed_scores'] = parsed_scores
    context['tentativa_id'] = tentativa.id if tentativa else None

    logger.debug(f"Contexto final (evaluate_discursive_answer_view): User={request.user.username}, TentativaID={context['tentativa_id']}, { {k: v for k, v in context.items() if k not in ['submitted_user_answer', 'submitted_exam_context', 'form', 'evaluation_result_text']} }")
    return render(request, 'generator/discursive_evaluation_result.html', context)

@login_required
def dashboard_view(request):
    context, _, _ = _get_base_context_and_service()
    tentativas_recentes = []
    stats = {}
    date_from_obj = None # Data inicial do filtro
    date_to_obj = None # Data final do filtro

    # --- Lógica para Ler Filtros GET ---
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')

    if date_from_str:
        try:
            date_from_obj = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError:
            messages.warning(request, "Formato de data inicial inválido. Use AAAA-MM-DD.")
            date_from_obj = None # Ignora filtro se inválido

    if date_to_str:
        try:
            date_to_obj = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            messages.warning(request, "Formato de data final inválido. Use AAAA-MM-DD.")
            date_to_obj = None # Ignora filtro se inválido

    logger.info(f"Dashboard acessado por {request.user.username}. Filtro Data: {date_from_str} a {date_to_str}")

    try:
        # Busca base de TODAS as tentativas do usuário
        todas_tentativas_qs = TentativaResposta.objects.filter(usuario=request.user)

        # --- Aplica Filtros de Data ---
        if date_from_obj:
            todas_tentativas_qs = todas_tentativas_qs.filter(data_resposta__date__gte=date_from_obj)
        if date_to_obj:
            todas_tentativas_qs = todas_tentativas_qs.filter(data_resposta__date__lte=date_to_obj)

        # --- Cálculos (sobre o queryset filtrado) ---
        total_geral = todas_tentativas_qs.count() # Total no período

        # Filtra C/E DENTRO do período para estatísticas
        tentativas_ce = todas_tentativas_qs.filter(questao__tipo='CE').prefetch_related('avaliacao')
        total_ce = tentativas_ce.count()
        acertos_ce = 0; erros_ce = 0
        for t_ce in tentativas_ce: # Itera SOMENTE nas C/E do período
            avaliacao = getattr(t_ce, 'avaliacao', None)
            try:
                if avaliacao is None and t_ce.pk: avaliacao = Avaliacao.objects.get(tentativa=t_ce)
            except Avaliacao.DoesNotExist: avaliacao = None
            if avaliacao and avaliacao.correto_ce is not None:
                if avaliacao.correto_ce: acertos_ce += 1
                else: erros_ce += 1
        score_ce = acertos_ce - erros_ce
        percentual_ce = round((acertos_ce / total_ce) * 100) if total_ce > 0 else 0

        # TODO: Calcular stats Discursivas para o período filtrado

        stats = {
            'total_geral': total_geral, # Agora é total NO PERÍODO
            'total_ce': total_ce, 'acertos_ce': acertos_ce, 'erros_ce': erros_ce,
            'score_ce': score_ce, 'percentual_ce': percentual_ce
            # Adicionar outras stats discursivas do período aqui
        }
        logger.info(f"Stats C/E (Filtrado) {request.user.username}: {stats}")

        # Pega as últimas 20 DENTRO do período filtrado para exibir na lista
        tentativas_recentes = todas_tentativas_qs.select_related(
            'questao', 'questao__area'
            ).prefetch_related(
                'avaliacao'
            ).order_by('-data_resposta')[:20] # Pega as 20 mais recentes DENTRO do filtro

    except Exception as e:
        logger.error(f"Erro dashboard {request.user.username}: {e}", exc_info=True)
        messages.error(request, "Erro carregar desempenho.")
        tentativas_recentes = []
        stats = {}

    context['tentativas_list'] = tentativas_recentes
    context['stats'] = stats
    # Passa as datas usadas no filtro de volta para o template preencher o form
    context['current_date_from'] = date_from_obj
    context['current_date_to'] = date_to_obj

    return render(request, 'generator/dashboard.html', context)

# --- NOVA VIEW: Resultado do Simulado ---
@login_required
def resultado_simulado_view(request):
    """Exibe os resultados e estatísticas do último simulado concluído."""
    context, _, _ = _get_base_context_and_service()
    # Pega os IDs das questões do simulado finalizado da sessão
    questao_ids = request.session.pop('finalizado_simulado_questao_ids', []) # Usa pop para pegar e remover

    if not questao_ids:
        messages.warning(request, "Não há resultados de simulado para exibir.")
        return redirect('generator:dashboard') # Ou para 'configurar_simulado'

    logger.info(f"Exibindo resultado do simulado para {request.user.username}. Questões IDs: {questao_ids}")

    tentativas = []
    stats = {}

    try:
        # Busca as tentativas e avaliações APENAS para as questões deste simulado
        tentativas = TentativaResposta.objects.filter(
            usuario=request.user,
            questao_id__in=questao_ids # Filtra pelos IDs do simulado
        ).select_related(
            'questao', 'questao__area'
        ).prefetch_related(
            'avaliacao'
        ).order_by('data_resposta') # Ordena pela ordem de resposta

        # Calcula Estatísticas Específicas do Simulado
        total_ce = 0; acertos_ce = 0; erros_ce = 0
        total_disc = 0; nc_total = 0.0; ne_total = 0; npd_total = 0.0; count_disc_avaliadas = 0

        for t in tentativas:
            if t.questao.tipo == 'CE':
                total_ce += 1
                avaliacao = getattr(t, 'avaliacao', None)
                try:
                    if avaliacao is None and t.pk: avaliacao = Avaliacao.objects.get(tentativa=t)
                except Avaliacao.DoesNotExist: avaliacao = None
                if avaliacao and avaliacao.correto_ce is not None:
                    if avaliacao.correto_ce: acertos_ce += 1
                    else: erros_ce += 1
            elif t.questao.tipo == 'DISC':
                total_disc += 1
                avaliacao = getattr(t, 'avaliacao', None)
                try:
                     if avaliacao is None and t.pk: avaliacao = Avaliacao.objects.get(tentativa=t)
                except Avaliacao.DoesNotExist: avaliacao = None
                # Soma apenas se a avaliação discursiva foi feita e tem notas
                if avaliacao and avaliacao.nc is not None and avaliacao.ne is not None and avaliacao.npd is not None:
                     nc_total += avaliacao.nc
                     ne_total += avaliacao.ne
                     npd_total += avaliacao.npd
                     count_disc_avaliadas += 1

        # Stats C/E
        score_ce = acertos_ce - erros_ce
        percentual_ce = round((acertos_ce / total_ce) * 100) if total_ce > 0 else 0
        # # Stats Discursivas (Médias)
        # media_nc = round(nc_total / count_disc_avaliadas, 2) if count_disc_avaliadas > 0 else None
        # media_ne = round(ne_total / count_disc_avaliadas, 2) if count_disc_avaliadas > 0 else None
        # media_npd = round(npd_total / count_disc_avaliadas, 2) if count_disc_avaliadas > 0 else None

        stats = {
            'total_questoes_simulado': len(questao_ids), # Total planejado
            'total_respondidas': tentativas.count(), # Total efetivamente respondido/salvo
            'total_ce': total_ce,
            'acertos_ce': acertos_ce,
            'erros_ce': erros_ce,
            'score_ce': score_ce,
            'percentual_ce': percentual_ce,
            'total_disc': total_disc,
            'total_disc_avaliadas': count_disc_avaliadas,
            # 'media_nc': media_nc,
            # 'media_ne': media_ne,
            # 'media_npd': media_npd,
        }
        logger.info(f"Stats do Simulado para {request.user.username}: {stats}")

    except Exception as e:
        logger.error(f"Erro ao buscar/calcular resultado do simulado para {request.user.username}: {e}", exc_info=True)
        messages.error(request, "Erro ao carregar os resultados do simulado.")
        # Não limpa a lista de tentativas para debug se necessário
        stats = {}

    context['tentativas_simulado'] = tentativas # Passa a lista de tentativas deste simulado
    context['stats_simulado'] = stats # Passa as estatísticas deste simulado

    return render(request, 'generator/resultado_simulado.html', context)
# --- FIM NOVA VIEW ---

# --- VIEW PARA O HUB DE JOGOS ---
@login_required
def games_hub_view(request):
    """Renderiza a página que lista os jogos disponíveis."""
    context, _, _ = _get_base_context_and_service()
    available_games = [
        {
            'name': 'Arrastar e Soltar: Algoritmos ML',
            'description': 'Associe algoritmos como SVM, KNN e K-Means às suas categorias.',
            'url_name': 'generator:drag_drop_ml_game',
            'icon': 'bi-arrows-move'
        },
    ]
    context['games'] = available_games
    # <<< CORREÇÃO: Aponta para o template dentro da pasta 'jogos' >>>
    return render(request, 'generator/jogos/games_hub.html', context)

# --- VIEW PARA O JOGO DE ARRASTAR E SOLTAR ---
@login_required
def drag_drop_ml_game_view(request):
    """Renderiza a página do jogo de arrastar e soltar sobre algoritmos de ML."""
    context, _, _ = _get_base_context_and_service()
    # <<< CORREÇÃO: Aponta para o template dentro da pasta 'jogos' >>>
    return render(request, 'generator/jogos/game_drag_drop_ml.html', context)


# --- Função de Teste (Mantida) ---
@login_required
def test_print_view(request):
    # ... (código como antes) ...
    message = f">>> TESTE PRINT VIEW EXECUTADO por {request.user.username} em {datetime.datetime.now()} <<<"; print(message); logger.info(f">>> Log INFO test_print_view (User: {request.user.username})"); logger.warning(">>> Log WARNING test_print_view"); return HttpResponse(f"<h1>Teste Concluído</h1><p>{message}</p><p>Logado como: {request.user.username}</p>")