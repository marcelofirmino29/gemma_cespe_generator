from collections import Counter
import json
import re
import logging
import traceback

from django.conf import settings
from django.http import JsonResponse, HttpRequest
from django.shortcuts import redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone

# Importações dos seus módulos do projeto 'generator'
from ..forms import (
    AskAIForm,
    QuestionGeneratorForm,
)
from ..models import (
    Avaliacao,
    Questao,
    TentativaResposta,
    AreaConhecimento,
    Topico,
)
from ..utils import STOP_WORDS_PT
from .. import scraper_logic

from .views_service_context import _get_base_context_and_service
from ..exceptions import AIResponseError, AIServiceError

logger = logging.getLogger(__name__)

@login_required
def landing_page_view(request: HttpRequest):
    context = {}
    context['error_message'] = None
    context['erro_destaques'] = None

    word_cloud_data = []
    try:
        questoes_recentes = Questao.objects.order_by('-criado_em')[:100]
        textos_combinados = ""
        for q in questoes_recentes:
            if q.texto_motivador: textos_combinados += q.texto_motivador + " "
            # CORRIGIDO: 'texto_comando' foi substituído por 'enunciado'
            if q.enunciado: textos_combinados += q.enunciado + " "
    
        if not textos_combinados:
            logger.info("LandingPage: Nenhum texto para nuvem.")
        else:
            textos_combinados = textos_combinados.lower()
            textos_combinados = re.sub(r'[.,!?;:()\[\]"\'“”‘’`]', ' ', textos_combinados)
            textos_combinados = re.sub(r'\s+', ' ', textos_combinados).strip()
            palavras = textos_combinados.split(' ')
            palavras_filtradas = [p for p in palavras if p not in STOP_WORDS_PT and len(p) > 3 and not p.isdigit()]
            if not palavras_filtradas:
                logger.info("LandingPage: Nenhuma palavra relevante para nuvem.")
            else:
                contagem = Counter(palavras_filtradas)
                word_cloud_data = [palavra for palavra, freq in contagem.most_common(50)]
                logger.info(f"LandingPage: Extraídas {len(word_cloud_data)} palavras para nuvem.")
    except Exception as e:
        logger.error(f"LandingPage: Erro nuvem: {e}", exc_info=True)
        word_cloud_data = ["Erro", "processar", "palavras"]
    context['word_cloud_data'] = word_cloud_data

    destaques_concursos_data = []
    try:
        logger.info("LandingPage: Buscando concursos destaque (CNB - Nacional)")
        target_url, err_cat = scraper_logic.get_target_url_and_validate_category_cnb('br')
        if err_cat: raise Exception(err_cat)
        soup, err_init = scraper_logic.init_web_scraper(target_url)
        if err_init: raise Exception(err_init)
        if soup:
            scraped_data, err_extract = scraper_logic.extract_concursos_data_cnb(soup)
            if err_extract and scraped_data is None: raise Exception(err_extract)
            if scraped_data:
                logger.info(f"LandingPage: Recebidos {len(scraped_data)} concursos. Selecionando até 10.")
                for item in scraped_data[:10]:
                    destaques_concursos_data.append({
                        "organizacao": item.get("organizacao", "N/I"), "vagas": str(item.get("vagasDisponiveis", "N/I")),
                        "status": item.get("status", "N/I").capitalize(), "link": item.get("link", "#")
                    })
            elif err_extract:
                logger.info(f"LandingPage: Mensagem extração CNB (sem dados): {err_extract}")
        else:
            logger.error("LandingPage: Falha obter soup CNB.")
    except Exception as e:
        context['erro_destaques'] = "Não foi possível carregar concursos em destaque."
        logger.error(f"LandingPage: Erro destaques: {e}", exc_info=False)
    
    context['concursos_destaque_marquee'] = destaques_concursos_data
    return render(request, 'generator/landing_page.html', context)


@login_required
def validate_answers_view(request: HttpRequest):
    context, _, _ = _get_base_context_and_service()
    performance_data = None; results_list = []; error_processing = None
    context['form'] = QuestionGeneratorForm(max_questions=getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 150))

    if request.method == 'POST':
        logger.info(f"POST validate_answers_view por {request.user.username}")
        try:
            all_post_keys = request.POST.keys()
            questao_ids_respondidas = [k.split('_')[-1] for k in all_post_keys if k.startswith('resposta_q')]
            if not questao_ids_respondidas:
                questao_ids_respondidas = [request.POST.get(f'questao_id_{i}') for i in sorted(list(set([int(k.split('_')[-1]) for k in all_post_keys if k.startswith('questao_id_')]))) if request.POST.get(f'questao_id_{i}')]
                if not questao_ids_respondidas:
                    raise ValueError("Nenhum ID de questão no POST.")
            
            logger.info(f"IDs para validação: {questao_ids_respondidas}")
            attempt_results = []
            total_processed = 0; correct_count = 0; incorrect_count = 0
            for q_id in questao_ids_respondidas:
                user_ans = request.POST.get(f'resposta_q{q_id}')
                if user_ans is None or user_ans.strip().upper() not in ['C', 'E']:
                    logger.warning(f"Questão ID {q_id}: Resposta inválida ('{user_ans}').")
                    error_processing = (error_processing or "") + f" Erro: Resposta inválida ID {q_id}."
                    continue
                try:
                    q_obj = Questao.objects.get(id=q_id, tipo='CE')
                    tent, _ = TentativaResposta.objects.update_or_create(
                        usuario=request.user, questao=q_obj,
                        defaults={'resposta_ce': user_ans.strip().upper(), 'data_resposta': timezone.now()}
                    )
                    is_correct = (tent.resposta_ce == q_obj.gabarito_ce)
                    score = 1 if is_correct else -1
                    Avaliacao.objects.update_or_create(
                        tentativa=tent, defaults={'correto_ce': is_correct, 'score_ce': score}
                    )
                    # CORRIGIDO: 'texto_comando' foi substituído por 'enunciado'
                    attempt_results.append({
                        'questao_id': q_obj.id, 'afirmacao': q_obj.enunciado,
                        'user_answer': tent.resposta_ce, 'gabarito': q_obj.gabarito_ce,
                        'correct': is_correct, 'justificativa': q_obj.justificativa_gabarito or "Não fornecida."
                    })
                    total_processed += 1
                    if is_correct: correct_count += 1
                    else: incorrect_count += 1
                except Questao.DoesNotExist:
                    logger.error(f"Questão C/E ID {q_id} não encontrada. Pulando.")
                    error_processing = (error_processing or "") + f" Erro: Questão ID {q_id} não encontrada."
                except Exception as db_error:
                    logger.error(f"Erro DB (Questao ID {q_id}): {db_error}", exc_info=True)
                    error_processing = (error_processing or "") + f" Erro ao processar questão ID {q_id}."
            
            results_list = attempt_results
            if not results_list and not error_processing: error_processing = "Nenhum item válido processado."
            if total_processed > 0:
                final_score = correct_count - incorrect_count
                percentage_correct = round((correct_count / total_processed) * 100)
                performance_data = {
                    'correct': correct_count, 'incorrect': incorrect_count,
                    'total': total_processed, 'score': final_score, 'percentage': percentage_correct
                }
                logger.info(f"Performance User {request.user.username}: Score {final_score}/{total_processed}.")
        except ValueError as e:
            logger.error(f"Erro ValueError na validação: {e}", exc_info=True)
            error_processing = f"Erro nos dados recebidos: {e}."
        except Exception as e:
            logger.exception(f"Erro inesperado na validação: {e}")
            error_processing = "Erro inesperado durante o processamento."
        
        context['results'] = results_list
        if performance_data: context['performance'] = performance_data
        if error_processing: context['error_message'] = error_processing
        return render(request, 'generator/question_generator.html', context)
    
    elif request.method == 'GET':
        logger.warning(f"Acesso GET a validate_answers_view por {request.user.username or 'Anônimo'}")
        messages.info(request, "Use o formulário para gerar questões.")
        return redirect('generator:generate_questions')
        
    context['error_message'] = context.get('error_message', "Acesso inválido.")
    return render(request, 'generator/question_generator.html', context)

@login_required
@require_POST
def validate_single_ce_view(request: HttpRequest):
    try:
        data = json.loads(request.body)
        questao_id = data.get('questao_id')
        user_answer = data.get('user_answer')
        logger.info(f"AJAX validate_single_ce por {request.user.username} para Questao ID: {questao_id}, Resposta: {user_answer}")
        if not questao_id or not isinstance(questao_id, (int, str)) or user_answer not in ['C', 'E']:
            logger.warning(f"Dados inválidos AJAX: ID={questao_id}, Resposta={user_answer}")
            return JsonResponse({'error': 'Dados inválidos (ID ou resposta).'}, status=400)
        
        try:
            questao_id_int = int(questao_id)
        except ValueError:
            logger.warning(f"ID da questão inválido (não numérico): {questao_id}")
            return JsonResponse({'error': 'ID da questão inválido.'}, status=400)
            
        try:
            q_obj = Questao.objects.get(id=questao_id_int, tipo='CE')
            tent, _ = TentativaResposta.objects.update_or_create(
                usuario=request.user, questao=q_obj,
                defaults={'resposta_ce': user_answer, 'data_resposta': timezone.now()}
            )
            is_correct = (tent.resposta_ce == q_obj.gabarito_ce)
            score = 1 if is_correct else -1
            Avaliacao.objects.update_or_create(
                tentativa=tent, defaults={'correto_ce': is_correct, 'score_ce': score}
            )
            response_data = {
                'correct': is_correct, 'gabarito': q_obj.gabarito_ce,
                'justification': q_obj.justificativa_gabarito or ""
            }
            logger.info(f"AJAX validate_single_ce SUCESSO para Questao ID {questao_id_int}. Correto: {is_correct}")
            return JsonResponse(response_data)
        except Questao.DoesNotExist:
            logger.error(f"Questão C/E ID {questao_id_int} não encontrada para AJAX.")
            return JsonResponse({'error': 'Questão não encontrada.'}, status=404)
        except Exception as e:
            logger.error(f"Erro DB/processamento AJAX para Questao ID {questao_id_int}: {e}", exc_info=True)
            return JsonResponse({'error': 'Erro interno ao processar.'}, status=500)
    except json.JSONDecodeError:
        logger.error("Erro ao decodificar JSON em validate_single_ce_view.")
        return JsonResponse({'error': 'Requisição JSON inválida.'}, status=400)
    except Exception as e:
        logger.error(f"Erro inesperado em validate_single_ce_view: {e}", exc_info=True)
        return JsonResponse({'error': 'Erro inesperado no servidor.'}, status=500)


@login_required
def ask_ai_view(request: HttpRequest):
    base_context, service, service_initialized = _get_base_context_and_service()
    
    context = {
        **base_context,
        'loading': False,
        'ai_response': None,
        'user_question_processed': None, 
        'form': AskAIForm()
    }
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'GET':
        question_from_url = request.GET.get('question')
        if question_from_url:
            context['user_question_processed'] = question_from_url
            logger.info(f"ASK_AI_VIEW (GET com param): User '{request.user.username}' pergunta da URL: '{question_from_url[:100]}...'")
            context['form'] = AskAIForm(initial={'user_input': question_from_url})
            
            if service_initialized and service:
                try:
                    ai_response_text = service.get_ai_response(user_prompt=question_from_url)
                    context['ai_response'] = ai_response_text
                    logger.info(f"ASK_AI_VIEW (GET com param): Resposta da IA para '{request.user.username}' obtida.")
                except AttributeError: 
                    logger.error(f"ASK_AI_VIEW (GET com param): Método 'get_ai_response' não encontrado no objeto service ({type(service)}).")
                    messages.error(request, "Erro interno: Função de IA indisponível.")
                    context['ai_response'] = "Erro: Função de IA indisponível no serviço."
                except (AIResponseError, AIServiceError) as e:
                    logger.error(f"ASK_AI_VIEW (GET com param): Erro AI/Service para '{request.user.username}': {e}\n{traceback.format_exc()}")
                    messages.error(request, f"Erro ao comunicar com a IA: {str(e)[:100]}")
                    context['ai_response'] = f"Erro ao obter resposta: {str(e)[:100]}"
                except Exception as e:
                    logger.error(f"ASK_AI_VIEW (GET com param): Erro inesperado para '{request.user.username}': {e}\n{traceback.format_exc()}")
                    messages.error(request, "Ocorreu um erro inesperado.")
                    context['ai_response'] = "Erro inesperado."
            else: 
                messages.error(request, "Serviço de IA indisponível.")
                context['ai_response'] = "Serviço de IA indisponível."

    elif request.method == 'POST':
        form_data_for_validation = None
        if is_ajax:
            try:
                data = json.loads(request.body)
                received_user_input = data.get('user_input')
                if received_user_input and received_user_input.strip():
                    form_data_for_validation = {'user_input': received_user_input}
                else:
                    logger.warning("ASK_AI_VIEW (AJAX POST): Nenhuma pergunta válida fornecida.")
                    return JsonResponse({'error': 'Nenhuma pergunta válida fornecida.'}, status=400)
            except json.JSONDecodeError:
                logger.error("ASK_AI_VIEW (AJAX POST): Dados JSON inválidos.")
                return JsonResponse({'error': 'Dados JSON inválidos.'}, status=400)
        else: 
            form_data_for_validation = request.POST
        
        form = AskAIForm(form_data_for_validation)
        context['form'] = form

        if form.is_valid():
            user_input_value = form.cleaned_data['user_input']
            context['user_question_processed'] = user_input_value

            logger.info(f"ASK_AI_VIEW (POST): User '{request.user.username}' pergunta: '{user_input_value[:100]}...' (AJAX: {is_ajax})")
            if not is_ajax: context['loading'] = True
            
            if service_initialized and service:
                try:
                    ai_response_text = service.get_ai_response(user_prompt=user_input_value)
                    logger.info(f"ASK_AI_VIEW (POST): Resposta da IA para '{request.user.username}' obtida.")
                    context['ai_response'] = ai_response_text
                    if is_ajax:
                        return JsonResponse({'answer': ai_response_text})
                    else:
                        messages.success(request, "Resposta da IA recebida.")
                        context['form'] = AskAIForm()
                except AttributeError: 
                    logger.error(f"ASK_AI_VIEW (POST): Método 'get_ai_response' não encontrado no objeto service ({type(service)}).")
                    error_message = "Erro interno: Função de IA indisponível no serviço."
                    if is_ajax: return JsonResponse({'error': error_message, 'details': 'AttributeError no servidor'}, status=500)
                    messages.error(request, error_message); context['ai_response'] = error_message
                except (AIResponseError, AIServiceError) as e:
                    logger.error(f"ASK_AI_VIEW (POST): Erro AI/Service para '{request.user.username}': {e}\n{traceback.format_exc()}")
                    error_message = f"Erro ao comunicar com a IA: {str(e)[:100]}"
                    if is_ajax: return JsonResponse({'error': error_message, 'details': str(e)}, status=500)
                    messages.error(request, error_message); context['ai_response'] = error_message
                except Exception as e:
                    logger.error(f"ASK_AI_VIEW (POST): Erro inesperado para '{request.user.username}': {e}\n{traceback.format_exc()}")
                    error_message = "Desculpe, ocorreu um erro inesperado."
                    if is_ajax: return JsonResponse({'error': error_message, 'details': str(e)}, status=500)
                    messages.error(request, error_message); context['ai_response'] = error_message
                finally:
                    if not is_ajax: context['loading'] = False
            else: 
                error_message = "Serviço de IA indisponível para processar a pergunta."
                logger.error(f"ASK_AI_VIEW (POST): Serviço de IA não inicializado ou não disponível para '{request.user.username}'.")
                if is_ajax: return JsonResponse({'error': error_message}, status=503)
                messages.error(request, error_message); context['ai_response'] = error_message
        else: 
            logger.warning(f"ASK_AI_VIEW (POST): Formulário 'AskAIForm' inválido por '{request.user.username}'. Erros: {form.errors.as_json()} (AJAX: {is_ajax})")
            if is_ajax:
                error_detail = form.errors.get('user_input', [{"message": "Erro de validação não especificado."}])[0].get('message', "Erro de validação.")
                return JsonResponse({'error': error_detail}, status=400)
            messages.error(request, "Por favor, corrija os erros no formulário.")

    return render(request, 'generator/ask_ai.html', context)

@login_required
@require_POST
def validate_single_me_view(request: HttpRequest):
    """
    Valida, via AJAX, uma questão de Múltipla Escolha (ME).
    - Salva/atualiza TentativaResposta.resposta_me.
    - Cria/atualiza Avaliacao.correto_me / score_me.
    - Retorna JSON com se acertou, gabarito e justificativa.
    """
    try:
        data = json.loads(request.body)
        questao_id = data.get('questao_id')
        user_answer = data.get('user_answer')

        logger.info(
            f"AJAX validate_single_me por {request.user.username} "
            f"para Questao ID: {questao_id}, Resposta: {user_answer}"
        )

        if not questao_id or not isinstance(questao_id, (int, str)) \
           or user_answer not in ['A', 'B', 'C', 'D', 'E']:
            logger.warning(f"Dados inválidos AJAX ME: ID={questao_id}, Resposta={user_answer}")
            return JsonResponse({'error': 'Dados inválidos (ID ou resposta).'}, status=400)

        try:
            questao_id_int = int(questao_id)
        except ValueError:
            logger.warning(f"ID da questão inválido (não numérico) ME: {questao_id}")
            return JsonResponse({'error': 'ID da questão inválido.'}, status=400)

        try:
            q_obj = Questao.objects.get(id=questao_id_int, tipo='ME')
            tent, _ = TentativaResposta.objects.update_or_create(
                usuario=request.user,
                questao=q_obj,
                defaults={
                    'resposta_me': user_answer,
                    'data_resposta': timezone.now()
                }
            )
            is_correct = (tent.resposta_me == q_obj.gabarito_me)
            score = 1 if is_correct else -1

            Avaliacao.objects.update_or_create(
                tentativa=tent,
                defaults={
                    'correto_me': is_correct,
                    'score_me': score
                }
            )

            response_data = {
                'correct': is_correct,
                'gabarito': q_obj.gabarito_me,
                'justification': q_obj.justificativa_gabarito or ""
            }
            logger.info(
                f"AJAX validate_single_me SUCESSO para Questao ID {questao_id_int}. "
                f"Correto: {is_correct}"
            )
            return JsonResponse(response_data)

        except Questao.DoesNotExist:
            logger.error(f"Questão ME ID {questao_id_int} não encontrada para AJAX.")
            return JsonResponse({'error': 'Questão não encontrada.'}, status=404)
        except Exception as e:
            logger.error(
                f"Erro DB/processamento AJAX ME para Questao ID {questao_id_int}: {e}",
                exc_info=True
            )
            return JsonResponse({'error': 'Erro interno ao processar.'}, status=500)

    except json.JSONDecodeError:
        logger.error("Erro ao decodificar JSON em validate_single_me_view.")
        return JsonResponse({'error': 'Requisição JSON inválida.'}, status=400)
    except Exception as e:
        logger.error(f"Erro inesperado em validate_single_me_view: {e}", exc_info=True)
        return JsonResponse({'error': 'Erro inesperado no servidor.'}, status=500)