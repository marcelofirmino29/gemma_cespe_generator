import logging
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.urls import reverse
from django.db.models import Q
from generator.exceptions import AIResponseError, AIServiceError, ConfigurationError, GeneratorError, ParsingError
from generator.forms import AreaConhecimentoForm, DiscursiveExamForm, QuestionGeneratorForm, SimuladoConfigForm
from generator.models import AreaConhecimento, Avaliacao, Questao, TentativaResposta, Topico
from django.utils import timezone
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST

# IMPORTAÇÃO MODIFICADA: Adicionado parse_discursive_question
from generator.utils import parse_evaluation_scores, parse_discursive_question
from generator.views.views_functions import extrair_texto_completo_pdf
from generator.views.views_service_context import _get_base_context_and_service

logger = logging.getLogger(__name__)


@login_required
def generate_questions_view(request):
    base_context, service, service_initialized = _get_base_context_and_service()
    context = base_context.copy()
    context['service_initialized'] = service_initialized
    max_q = getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 150)
    form_instance = QuestionGeneratorForm(max_questions=max_q)
    context['page_obj'] = None
    context['main_motivador'] = None

    if request.method == 'POST':
        logger.info(f"POST generate_questions_view por {request.user.username}")
        request.session.pop('latest_ce_ids', None)
        request.session.pop('latest_ce_motivador', None)
        form_instance = QuestionGeneratorForm(request.POST, request.FILES, max_questions=max_q)

        pdf_file_uploaded = 'pdf_contexto' in request.FILES and request.FILES.get('pdf_contexto')
        if pdf_file_uploaded:
            if 'topic' in form_instance.fields:
                form_instance.fields['topic'].required = False
                logger.info("Campo 'topic' tornado NÃO obrigatório porque um PDF foi enviado.")
        else:
            if 'topic' in form_instance.fields:
                form_instance.fields['topic'].required = True
                logger.info("Nenhum PDF enviado, campo 'topic' permanece/torna-se obrigatório.")

        context['form'] = form_instance

        if form_instance.is_valid():
            logger.info("Formulário de Geração C/E é VÁLIDO.")
            if not service_initialized or not service:
                messages.error(request, context.get('error_message', "Serviço de IA indisponível para processar."))
                return render(request, 'generator/question_generator.html', context)

            num_questions = form_instance.cleaned_data.get('num_questions')
            difficulty = form_instance.cleaned_data.get('difficulty_level')
            area_obj = form_instance.cleaned_data.get('area')
            contexto_para_ia = ""
            fonte_contexto = ""
            pdf_file_cleaned = form_instance.cleaned_data.get('pdf_contexto')
            topic_text_cleaned = form_instance.cleaned_data.get('topic', '').strip()

            if pdf_file_cleaned:
                try:
                    contexto_para_ia = extrair_texto_completo_pdf(pdf_file_cleaned)
                    fonte_contexto = f"PDF: {pdf_file_cleaned.name}"
                    if not contexto_para_ia.strip():
                        messages.error(
                            request,
                            f"Não foi possível extrair conteúdo textual útil do PDF '{pdf_file_cleaned.name}'. "
                            "O arquivo pode ser uma imagem, estar protegido, ser muito complexo ou estar vazio. "
                            "Tente o contexto textual."
                        )
                        return render(request, 'generator/question_generator.html', context)
                    logger.info(
                        f"Contexto para IA obtido do PDF: '{pdf_file_cleaned.name}' "
                        f"({len(contexto_para_ia)} caracteres). Início: '{contexto_para_ia[:250]}...'"
                    )
                except ValueError as ve:
                    messages.error(request, str(ve))
                    return render(request, 'generator/question_generator.html', context)
                except Exception as e_pdf_extract:
                    logger.error(
                        f"Erro crítico ao extrair texto do PDF '{pdf_file_cleaned.name}': {e_pdf_extract}",
                        exc_info=True
                    )
                    messages.error(request, "Ocorreu um erro inesperado ao tentar ler o arquivo PDF.")
                    return render(request, 'generator/question_generator.html', context)
            elif topic_text_cleaned:
                contexto_para_ia = topic_text_cleaned
                fonte_contexto = "Tópico Textual"
                logger.info(
                    f"Usando contexto do campo Tópico ({len(contexto_para_ia)} caracteres). "
                    f"Início: '{contexto_para_ia[:250]}...'"
                )

            if not contexto_para_ia.strip():
                messages.error(request, "Contexto para IA está vazio. Forneça um tópico ou PDF com conteúdo legível.")
                return render(request, 'generator/question_generator.html', context)

            logger.info(
                f"Preparando para chamar IA (C/E). Fonte: {fonte_contexto}, "
                f"Num Questões: {num_questions}, Dificuldade: {difficulty}."
            )
            try:
                main_motivador, generated_items_data = service.generate_questions(
                    topic=contexto_para_ia,
                    num_questions=num_questions,
                    difficulty_level=difficulty
                )
                if not generated_items_data or not isinstance(generated_items_data, list):
                    messages.warning(request, "IA retornou dados inválidos.")
                    generated_items_data = []

                saved_question_ids = []
                if generated_items_data:
                    logger.info(f"Salvando {len(generated_items_data)} itens C/E...")
                    generic_topic, _ = Topico.objects.get_or_create(
                        nome=f"Tópico Geral de {area_obj.nome}",
                        defaults={'area_conhecimento': area_obj}
                    )
                    for item_data in generated_items_data:
                        try:
                            if not isinstance(item_data, dict):
                                continue
                            gabarito = item_data.get('gabarito')
                            afirmacao = item_data.get('afirmacao')
                            if not gabarito or gabarito not in ['C', 'E'] or not afirmacao or not afirmacao.strip():
                                continue

                            q = Questao(
                                tipo='CE',
                                texto_motivador=main_motivador,
                                enunciado=afirmacao,
                                gabarito_ce=gabarito,
                                justificativa_gabarito=item_data.get('justificativa'),
                                dificuldade=(difficulty or 'medio'),
                                topico=generic_topic,
                                criado_por=request.user
                            )
                            q.save()
                            saved_question_ids.append(q.id)
                        except Exception as save_error:
                            logger.error(f"Erro salvar C/E item: {save_error}", exc_info=True)

                if saved_question_ids:
                    messages.success(request, f"{len(saved_question_ids)} questões C/E geradas!")
                    request.session['latest_ce_ids'] = saved_question_ids
                    request.session['latest_ce_motivador'] = main_motivador if main_motivador else ""
                else:
                    if generated_items_data:
                        messages.warning(
                            request,
                            "Nenhuma questão válida foi salva (verifique formato/dados da IA)."
                        )
                    else:
                        messages.warning(
                            request,
                            "IA não retornou questões válidas para salvar."
                        )
                if generated_items_data and len(saved_question_ids) < len(generated_items_data):
                    messages.warning(
                        request,
                        "Alguns itens podem não ter sido salvos (problemas de formato ou dados)."
                    )

                return redirect(reverse('generator:generate_questions'))

            except Exception as e:
                logger.error(f"Erro INESPERADO na Geração ou Salvamento C/E: {e}", exc_info=True)
                context['error_message'] = f"Erro inesperado: {e}"
                messages.error(request, context['error_message'])
                return render(request, 'generator/question_generator.html', context)
        else:
            logger.warning(f"Formulário de Geração C/E INVÁLIDO: {form_instance.errors.as_json()}")
            messages.error(request, "Por favor, corrija os erros indicados no formulário.")
            return render(request, 'generator/question_generator.html', context)

    # --- Lógica GET ---
    else:
        form_instance = QuestionGeneratorForm(max_questions=max_q)
        context['form'] = form_instance
        logger.debug(f"GET generate_questions_view por {request.user.username}")
        if request.GET.get('action') == 'clear':
            logger.info("Limpando sessão 'latest_ce' via action=clear.")
            request.session.pop('latest_ce_ids', None)
            request.session.pop('latest_ce_motivador', None)
            messages.info(request, "Resultado anterior limpo.")
            return redirect(reverse('generator:generate_questions'))

        latest_ids = request.session.get('latest_ce_ids')
        context['main_motivador'] = request.session.get('latest_ce_motivador')
        context['page_obj'] = None
        context['paginator'] = None

        if latest_ids:
            logger.info(f"GET: IDs encontrados na sessão para paginação (C/E): {latest_ids}.")
            try:
                question_list = (
                    Questao.objects
                    .filter(id__in=latest_ids)
                    .select_related('topico__area_conhecimento', 'criado_por')
                    .order_by('id')
                )
                logger.info(f"GET: Número de questões C/E encontradas no DB: {question_list.count()}")

                if question_list.exists():
                    items_per_page = getattr(settings, 'ITEMS_PER_PAGE_GENERATOR', 20)
                    paginator_instance = Paginator(question_list, items_per_page)
                    logger.info(
                        f"GET: Paginator C/E. Total de itens: {paginator_instance.count}, "
                        f"Total de páginas: {paginator_instance.num_pages}"
                    )
                    page_number = request.GET.get('page')
                    try:
                        page_obj = paginator_instance.get_page(page_number)
                    except PageNotAnInteger:
                        page_obj = paginator_instance.get_page(1)
                    except EmptyPage:
                        page_obj = paginator_instance.get_page(paginator_instance.num_pages)

                    context['page_obj'] = page_obj
                    context['paginator'] = paginator_instance
                    logger.info(
                        f"GET: Paginação C/E configurada. "
                        f"Página: {page_obj.number} de {paginator_instance.num_pages}."
                    )
                else:
                    logger.warning(
                        f"GET: IDs {latest_ids} na sessão, mas NENHUMA questão C/E encontrada. "
                        "Limpando sessão."
                    )
                    request.session.pop('latest_ce_ids', None)
                    request.session.pop('latest_ce_motivador', None)
                    context['main_motivador'] = None
            except Exception as e:
                logger.error(f"GET: Erro ao buscar/paginar questões C/E da sessão: {e}", exc_info=True)
                messages.error(request, "Erro ao carregar ou paginar as questões C/E da sessão.")
                request.session.pop('latest_ce_ids', None)
                request.session.pop('latest_ce_motivador', None)
                context['main_motivador'] = None
        else:
            logger.info("GET: Nenhum 'latest_ce_ids' encontrado na sessão.")
            pass

    return render(request, 'generator/question_generator.html', context)


@login_required
def generate_me_questions_view(request):
    """
    Versão de geração para múltipla escolha (ME).
    Fluxo idêntico ao C/E, mas chama service.generate_me_questions
    e salva Questao(tipo='ME', alternativas A–E, gabarito_me).
    """
    base_context, service, service_initialized = _get_base_context_and_service()
    context = base_context.copy()
    context['service_initialized'] = service_initialized
    max_q = getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 150)
    form_instance = QuestionGeneratorForm(max_questions=max_q)
    context['page_obj'] = None
    context['main_motivador'] = None

    if request.method == 'POST':
        logger.info(f"POST generate_me_questions_view por {request.user.username}")
        request.session.pop('latest_me_ids', None)
        request.session.pop('latest_me_motivador', None)
        form_instance = QuestionGeneratorForm(request.POST, request.FILES, max_questions=max_q)

        pdf_file_uploaded = 'pdf_contexto' in request.FILES and request.FILES.get('pdf_contexto')
        if pdf_file_uploaded:
            if 'topic' in form_instance.fields:
                form_instance.fields['topic'].required = False
                logger.info("ME: Campo 'topic' tornado NÃO obrigatório porque um PDF foi enviado.")
        else:
            if 'topic' in form_instance.fields:
                form_instance.fields['topic'].required = True
                logger.info("ME: Nenhum PDF enviado, campo 'topic' permanece/torna-se obrigatório.")

        context['form'] = form_instance

        if form_instance.is_valid():
            logger.info("Formulário de Geração ME é VÁLIDO.")
            if not service_initialized or not service:
                messages.error(request, context.get('error_message', "Serviço de IA indisponível para processar."))
                return render(request, 'generator/question_generator_me.html', context)

            num_questions = form_instance.cleaned_data.get('num_questions')
            difficulty = form_instance.cleaned_data.get('difficulty_level')
            area_obj = form_instance.cleaned_data.get('area')
            contexto_para_ia = ""
            fonte_contexto = ""
            pdf_file_cleaned = form_instance.cleaned_data.get('pdf_contexto')
            topic_text_cleaned = form_instance.cleaned_data.get('topic', '').strip()

            if pdf_file_cleaned:
                try:
                    contexto_para_ia = extrair_texto_completo_pdf(pdf_file_cleaned)
                    fonte_contexto = f"PDF: {pdf_file_cleaned.name}"
                    if not contexto_para_ia.strip():
                        messages.error(
                            request,
                            f"Não foi possível extrair conteúdo textual útil do PDF '{pdf_file_cleaned.name}'. "
                            "O arquivo pode ser uma imagem, estar protegido, ser muito complexo ou estar vazio. "
                            "Tente o contexto textual."
                        )
                        return render(request, 'generator/question_generator_me.html', context)
                    logger.info(
                        f"ME: Contexto para IA obtido do PDF: '{pdf_file_cleaned.name}' "
                        f"({len(contexto_para_ia)} caracteres). Início: '{contexto_para_ia[:250]}...'"
                    )
                except ValueError as ve:
                    messages.error(request, str(ve))
                    return render(request, 'generator/question_generator_me.html', context)
                except Exception as e_pdf_extract:
                    logger.error(
                        f"ME: Erro crítico ao extrair texto do PDF '{pdf_file_cleaned.name}': {e_pdf_extract}",
                        exc_info=True
                    )
                    messages.error(request, "Ocorreu um erro inesperado ao tentar ler o arquivo PDF.")
                    return render(request, 'generator/question_generator_me.html', context)
            elif topic_text_cleaned:
                contexto_para_ia = topic_text_cleaned
                fonte_contexto = "Tópico Textual"
                logger.info(
                    f"ME: Usando contexto do campo Tópico ({len(contexto_para_ia)} caracteres). "
                    f"Início: '{contexto_para_ia[:250]}...'"
                )

            if not contexto_para_ia.strip():
                messages.error(
                    request,
                    "Contexto para IA está vazio. Forneça um tópico ou PDF com conteúdo legível."
                )
                return render(request, 'generator/question_generator_me.html', context)

            logger.info(
                f"ME: Preparando para chamar IA. Fonte: {fonte_contexto}, "
                f"Num Questões: {num_questions}, Dificuldade: {difficulty}."
            )
            try:
                main_motivador, generated_items_data = service.generate_me_questions(
                    topic=contexto_para_ia,
                    num_questions=num_questions,
                    difficulty_level=difficulty,
                    area=area_obj
                )
                if not generated_items_data or not isinstance(generated_items_data, list):
                    messages.warning(request, "IA retornou dados inválidos para múltipla escolha.")
                    generated_items_data = []

                saved_question_ids = []
                if generated_items_data:
                    logger.info(f"Salvando {len(generated_items_data)} questões ME...")
                    generic_topic, _ = Topico.objects.get_or_create(
                        nome=f"Tópico ME Geral de {area_obj.nome}",
                        defaults={'area_conhecimento': area_obj}
                    )
                    for item_data in generated_items_data:
                        try:
                            if not isinstance(item_data, dict):
                                continue
                            enunciado = item_data.get('enunciado')
                            gabarito = item_data.get('gabarito')
                            if not enunciado or not enunciado.strip() or gabarito not in ['A', 'B', 'C', 'D', 'E']:
                                continue

                            q = Questao(
                                tipo='ME',
                                texto_motivador=main_motivador,
                                enunciado=enunciado,
                                alternativa_a=item_data.get('alternativa_a'),
                                alternativa_b=item_data.get('alternativa_b'),
                                alternativa_c=item_data.get('alternativa_c'),
                                alternativa_d=item_data.get('alternativa_d'),
                                alternativa_e=item_data.get('alternativa_e'),
                                gabarito_me=gabarito,
                                justificativa_gabarito=item_data.get('justificativa'),
                                dificuldade=(difficulty or 'medio'),
                                topico=generic_topic,
                                criado_por=request.user
                            )
                            q.save()
                            saved_question_ids.append(q.id)
                        except Exception as save_error:
                            logger.error(f"Erro salvar questão ME: {save_error}", exc_info=True)

                if saved_question_ids:
                    messages.success(request, f"{len(saved_question_ids)} questões de múltipla escolha geradas!")
                    request.session['latest_me_ids'] = saved_question_ids
                    request.session['latest_me_motivador'] = main_motivador if main_motivador else ""
                else:
                    if generated_items_data:
                        messages.warning(
                            request,
                            "Nenhuma questão ME válida foi salva (verifique formato/dados da IA)."
                        )
                    else:
                        messages.warning(
                            request,
                            "IA não retornou questões ME válidas para salvar."
                        )
                if generated_items_data and len(saved_question_ids) < len(generated_items_data):
                    messages.warning(
                        request,
                        "Algumas questões ME podem não ter sido salvas (formato/dados inconsistentes)."
                    )

                return redirect(reverse('generator:generate_me_questions'))

            except Exception as e:
                logger.error(f"Erro INESPERADO na Geração ou Salvamento ME: {e}", exc_info=True)
                context['error_message'] = f"Erro inesperado: {e}"
                messages.error(request, context['error_message'])
                return render(request, 'generator/question_generator_me.html', context)
        else:
            logger.warning(f"Formulário de Geração ME INVÁLIDO: {form_instance.errors.as_json()}")
            messages.error(request, "Por favor, corrija os erros indicados no formulário ME.")
            return render(request, 'generator/question_generator_me.html', context)

    # --- Lógica GET (ME) ---
    else:
        form_instance = QuestionGeneratorForm(max_questions=max_q)
        context['form'] = form_instance
        logger.debug(f"GET generate_me_questions_view por {request.user.username}")
        if request.GET.get('action') == 'clear':
            logger.info("ME: Limpando sessão 'latest_me' via action=clear.")
            request.session.pop('latest_me_ids', None)
            request.session.pop('latest_me_motivador', None)
            messages.info(request, "Resultado anterior de múltipla escolha limpo.")
            return redirect(reverse('generator:generate_me_questions'))

        latest_ids = request.session.get('latest_me_ids')
        context['main_motivador'] = request.session.get('latest_me_motivador')
        context['page_obj'] = None
        context['paginator'] = None

        if latest_ids:
            logger.info(f"ME GET: IDs encontrados na sessão para paginação: {latest_ids}.")
            try:
                question_list = (
                    Questao.objects
                    .filter(id__in=latest_ids, tipo='ME')
                    .select_related('topico__area_conhecimento', 'criado_por')
                    .order_by('id')
                )
                logger.info(f"ME GET: Número de questões ME encontradas no DB: {question_list.count()}")

                if question_list.exists():
                    items_per_page = getattr(settings, 'ITEMS_PER_PAGE_GENERATOR', 20)
                    paginator_instance = Paginator(question_list, items_per_page)
                    logger.info(
                        f"ME GET: Paginator ME. Total de itens: {paginator_instance.count}, "
                        f"Total de páginas: {paginator_instance.num_pages}"
                    )
                    page_number = request.GET.get('page')
                    try:
                        page_obj = paginator_instance.get_page(page_number)
                    except PageNotAnInteger:
                        page_obj = paginator_instance.get_page(1)
                    except EmptyPage:
                        page_obj = paginator_instance.get_page(paginator_instance.num_pages)

                    context['page_obj'] = page_obj
                    context['paginator'] = paginator_instance
                    logger.info(
                        f"ME GET: Paginação configurada. "
                        f"Página: {page_obj.number} de {paginator_instance.num_pages}."
                    )
                else:
                    logger.warning(
                        f"ME GET: IDs {latest_ids} na sessão, mas NENHUMA questão ME encontrada. Limpando sessão."
                    )
                    request.session.pop('latest_me_ids', None)
                    request.session.pop('latest_me_motivador', None)
                    context['main_motivador'] = None
            except Exception as e:
                logger.error(f"ME GET: Erro ao buscar/paginar questões ME da sessão: {e}", exc_info=True)
                messages.error(request, "Erro ao carregar ou paginar as questões ME da sessão.")
                request.session.pop('latest_me_ids', None)
                request.session.pop('latest_me_motivador', None)
                context['main_motivador'] = None
        else:
            logger.info("ME GET: Nenhum 'latest_me_ids' encontrado na sessão.")
            pass

    return render(request, 'generator/question_generator_me.html', context)
# (daqui pra baixo mantenha TODO o restante do arquivo exatamente como está hoje: demais views)

# @login_required
# def generate_discursive_exam_view(request):
#     base_context, service, service_initialized = _get_base_context_and_service()
#     context = base_context.copy()
#     context['service_initialized'] = service_initialized
#     discursive_exam_text = None
#     questao_id = None

#     if request.method == 'POST':
#         form = DiscursiveExamForm(request.POST, request.FILES or None)
#         if form.is_valid():
#             if not service_initialized or not service:
#                 messages.error(request, context.get('error_message', "Serviço de IA indisponível para processar."))
#                 context['form'] = form
#                 return render(request, 'generator/discursive_exam_generator.html', context)

#             base_topic_or_context_manual = form.cleaned_data.get('base_topic_or_context')
#             pdf_file_uploaded = form.cleaned_data.get('pdf_file')
#             final_context_for_ia = base_topic_or_context_manual

#             if pdf_file_uploaded:
#                 try:
#                     logger.info(f"Processando PDF '{pdf_file_uploaded.name}' para NOVA questão discursiva.")
#                     texto_do_pdf = extrair_texto_completo_pdf(pdf_file_uploaded)
#                     if texto_do_pdf and texto_do_pdf.strip():
#                         final_context_for_ia = texto_do_pdf
#                         if base_topic_or_context_manual and base_topic_or_context_manual.strip():
#                             final_context_for_ia += "\n\n--- Tópico adicional fornecido manualmente ---\n" + base_topic_or_context_manual
#                             messages.info(request, "Conteúdo do PDF combinado com texto manual para nova questão.")
#                         logger.info(f"Texto extraído do PDF para nova questão: {len(final_context_for_ia)} caracteres.")
#                     elif not (base_topic_or_context_manual and base_topic_or_context_manual.strip()):
#                         messages.error(request, f"PDF '{pdf_file_uploaded.name}' não contém texto extraível e nenhum tópico manual foi fornecido.")
#                         context['form'] = form
#                         context['error_message'] = "Fonte de contexto insuficiente."
#                         return render(request, 'generator/discursive_exam_generator.html', context)
#                 except ValueError as e_pdf:
#                     logger.error(f"Erro ao processar PDF para nova questão: {e_pdf}", exc_info=True)
#                     messages.error(request, f"Erro ao processar o arquivo PDF: {e_pdf}")
#                     if not (base_topic_or_context_manual and base_topic_or_context_manual.strip()):
#                         context['form'] = form
#                         context['error_message'] = "Erro no PDF e nenhum tópico manual fornecido."
#                         return render(request, 'generator/discursive_exam_generator.html', context)
            
#             if not final_context_for_ia or not final_context_for_ia.strip():
#                 messages.error(request, "É necessário fornecer um tópico/contexto textual ou um PDF com conteúdo para gerar a questão.")
#                 context['form'] = form
#                 return render(request, 'generator/discursive_exam_generator.html', context)

#             num_aspects = form.cleaned_data.get('num_aspects', 3)
#             area_obj = form.cleaned_data.get('area')
#             difficulty = form.cleaned_data.get('complexity', 'Intermediária')
#             complexity_for_service = difficulty
#             language = form.cleaned_data.get('language', 'pt-br')
#             current_user = request.user if request.user.is_authenticated else None
            
#             logger.info(f"POST Gerador Discursiva: Contexto_len={len(final_context_for_ia)}, Aspectos={num_aspects}, Área={area_obj}, Dificuldade={complexity_for_service}")

#             try:
#                 generated_text = service.generate_discursive_exam_question(
#                     base_topic_or_context=final_context_for_ia, 
#                     num_aspects=num_aspects, 
#                     area=area_obj.nome if area_obj else None, 
#                     complexity=complexity_for_service, 
#                     language=language
#                 )
                
#                 if generated_text and isinstance(generated_text, str) and generated_text.strip():
#                     dificuldade_db = 'medio'
#                     if complexity_for_service:
#                         comp_lower = complexity_for_service.lower()
#                         if comp_lower in ['fácil', 'facil', 'simples']: dificuldade_db = 'facil'
#                         elif comp_lower in ['difícil', 'dificil', 'complexa']: dificuldade_db = 'dificil'

#                     # CORRIGIDO: 'texto_comando' -> 'enunciado', 'area' -> 'topico'
#                     generic_topic, _ = Topico.objects.get_or_create(
#                         nome=f"Tópico Discursivo de {area_obj.nome}",
#                         defaults={'area_conhecimento': area_obj}
#                     )
#                     q = Questao(
#                         tipo='DISC',
#                         enunciado=generated_text,
#                         aspectos_discursiva=f"Avaliar {num_aspects} aspecto(s) solicitado(s).",
#                         dificuldade=dificuldade_db,
#                         topico=generic_topic,
#                         criado_por=current_user
#                     )
#                     q.save()
#                     questao_id = q.id
#                     discursive_exam_text = generated_text
#                     logger.info(f"Questão Discursiva ID {questao_id} salva com sucesso.")
#                     messages.success(request, f"Questão discursiva (ID: {questao_id}) gerada com sucesso! Você pode respondê-la abaixo ou buscar por ela mais tarde.")
#                     form = DiscursiveExamForm()
#                 else:
#                     messages.warning(request, "A IA não retornou um texto válido para a questão discursiva.")
#             except Exception as e:
#                 logger.error(f"Erro ao gerar ou salvar questão discursiva: {e}", exc_info=True)
#                 messages.error(request, f"Falha durante a geração/salvamento da questão: {e}")
#         else:
#             logger.warning(f"Formulário Gerador Discursiva INVÁLIDO: {form.errors.as_json()}")
#             messages.error(request, "Por favor, corrija os erros indicados no formulário.")
        
#         context['form'] = form

#     else: # GET
#         form = DiscursiveExamForm()
#         questao_id_from_url = request.GET.get('questao_id')
#         logger.debug(f"GET generate_discursive_exam por {request.user.username}. questao_id_from_url: {questao_id_from_url}")

#         if questao_id_from_url and questao_id_from_url.isdigit():
#             qid = int(questao_id_from_url)
#             logger.info(f"Tentando carregar Questão Discursiva ID={qid} via GET.")
#             try:
#                 questao_para_exibir = get_object_or_404(Questao, id=qid, tipo='DISC')
#                 # CORRIGIDO: 'texto_comando' -> 'enunciado'
#                 discursive_exam_text = questao_para_exibir.enunciado
#                 questao_id = questao_para_exibir.id
#                 logger.info(f"Questão Discursiva ID {questao_id} carregada para exibição e resolução.")
#                 messages.info(request, f"Modo Resolução: Questão ID {questao_id} carregada. Responda abaixo.")
#             except Questao.DoesNotExist:
#                 logger.warning(f"Questão discursiva ID {qid} não encontrada.", exc_info=False)
#                 messages.warning(request, f"A questão discursiva com ID {qid} não foi encontrada.")
#             except Exception as e:
#                 logger.error(f"Erro ao buscar questão discursiva ID {qid} via GET: {e}", exc_info=True)
#                 messages.error(request, f"Erro ao tentar carregar a questão discursiva com ID {qid}.")
        
#         context['form'] = form

#     context['discursive_exam_text'] = discursive_exam_text
#     context['questao_id'] = questao_id
#     return render(request, 'generator/discursive_exam_generator.html', context)

@login_required
def generate_discursive_exam_view(request):
    base_context, service, service_initialized = _get_base_context_and_service()
    context = base_context.copy()
    context['service_initialized'] = service_initialized
    discursive_exam_text = None
    questao_id = None
    questao_data = None  # Variável para os dados estruturados

    if request.method == 'POST':
        form = DiscursiveExamForm(request.POST, request.FILES or None)
        if form.is_valid():
            if not service_initialized or not service:
                messages.error(request, context.get('error_message', "Serviço de IA indisponível para processar."))
                context['form'] = form
                return render(request, 'generator/discursive_exam_generator.html', context)

            base_topic_or_context_manual = form.cleaned_data.get('base_topic_or_context')
            pdf_file_uploaded = form.cleaned_data.get('pdf_file')
            final_context_for_ia = base_topic_or_context_manual

            if pdf_file_uploaded:
                try:
                    logger.info(f"Processando PDF '{pdf_file_uploaded.name}' para NOVA questão discursiva.")
                    texto_do_pdf = extrair_texto_completo_pdf(pdf_file_uploaded)
                    if texto_do_pdf and texto_do_pdf.strip():
                        final_context_for_ia = texto_do_pdf
                        if base_topic_or_context_manual and base_topic_or_context_manual.strip():
                            final_context_for_ia += "\n\n--- Tópico adicional fornecido manualmente ---\n" + base_topic_or_context_manual
                            messages.info(request, "Conteúdo do PDF combinado com texto manual para nova questão.")
                    elif not (base_topic_or_context_manual and base_topic_or_context_manual.strip()):
                        messages.error(request, f"PDF '{pdf_file_uploaded.name}' não contém texto extraível e nenhum tópico manual foi fornecido.")
                        context['form'] = form
                        return render(request, 'generator/discursive_exam_generator.html', context)
                except ValueError as e_pdf:
                    logger.error(f"Erro ao processar PDF: {e_pdf}")
                    messages.error(request, f"Erro ao processar o arquivo PDF: {e_pdf}")
            
            if not final_context_for_ia or not final_context_for_ia.strip():
                messages.error(request, "É necessário fornecer um tópico/contexto textual ou um PDF para gerar a questão.")
                context['form'] = form
                return render(request, 'generator/discursive_exam_generator.html', context)

            num_aspects = form.cleaned_data.get('num_aspects', 3)
            area_obj = form.cleaned_data.get('area')
            difficulty = form.cleaned_data.get('complexity', 'Intermediária')
            language = form.cleaned_data.get('language', 'pt-br')
            current_user = request.user if request.user.is_authenticated else None
            
            try:
                generated_text = service.generate_discursive_exam_question(
                    base_topic_or_context=final_context_for_ia, 
                    num_aspects=num_aspects, 
                    area=area_obj.nome if area_obj else None, 
                    complexity=difficulty, 
                    language=language
                )
                
                if generated_text and isinstance(generated_text, str) and generated_text.strip():
                    # Lógica de dificuldade para o banco
                    dificuldade_db = 'medio'
                    comp_lower = difficulty.lower()
                    if comp_lower in ['fácil', 'facil', 'simples']: dificuldade_db = 'facil'
                    elif comp_lower in ['difícil', 'dificil', 'complexa']: dificuldade_db = 'dificil'

                    generic_topic, _ = Topico.objects.get_or_create(
                        nome=f"Tópico Discursivo de {area_obj.nome}",
                        defaults={'area_conhecimento': area_obj}
                    )
                    
                    q = Questao(
                        tipo='DISC',
                        enunciado=generated_text,
                        aspectos_discursiva=f"Avaliar {num_aspects} aspecto(s) solicitado(s).",
                        dificuldade=dificuldade_db,
                        topico=generic_topic,
                        criado_por=current_user
                    )
                    q.save()
                    
                    questao_id = q.id
                    discursive_exam_text = generated_text
                    
                    # MODIFICAÇÃO: Processando o texto gerado para evitar o "blocão"
                    questao_data = parse_discursive_question(generated_text)
                    
                    messages.success(request, f"Questão discursiva (ID: {questao_id}) gerada com sucesso!")
                    form = DiscursiveExamForm()
                else:
                    messages.warning(request, "A IA não retornou um texto válido.")
            except Exception as e:
                logger.error(f"Erro ao gerar ou salvar discursiva: {e}", exc_info=True)
                messages.error(request, f"Falha na geração: {e}")
        else:
            context['form'] = form

    else: # GET
        form = DiscursiveExamForm()
        questao_id_from_url = request.GET.get('questao_id')

        if questao_id_from_url and questao_id_from_url.isdigit():
            try:
                questao_para_exibir = get_object_or_404(Questao, id=int(questao_id_from_url), tipo='DISC')
                discursive_exam_text = questao_para_exibir.enunciado
                questao_id = questao_para_exibir.id
                
                # MODIFICAÇÃO: Parsing da questão carregada para exibir formatado no GET
                questao_data = parse_discursive_question(discursive_exam_text)
                
                messages.info(request, f"Modo Resolução: Questão ID {questao_id} carregada.")
            except Exception as e:
                logger.error(f"Erro ao carregar questão ID {questao_id_from_url}: {e}")
        
        context['form'] = form

    # MODIFICAÇÃO: Passando questao_data para o template
    context['discursive_exam_text'] = discursive_exam_text
    context['questao_id'] = questao_id
    context['questao_data'] = questao_data 
    
    return render(request, 'generator/discursive_exam_generator.html', context)

@login_required
def evaluate_discursive_answer_view(request):
    """
    View responsável por processar a resposta do usuário, solicitar a avaliação
    pela IA (escala 100 e fórmula Cebraspe) e exibir o resultado estruturado.
    """
    # Inicializa o contexto base e o serviço de IA
    context, service, service_initialized = _get_base_context_and_service()
    
    # Variáveis de controle para o template
    evaluation_result_text = None
    evaluation_error = None
    submitted_exam_context = None
    submitted_user_answer = None
    questao_original_data = None
    parsed_scores = None
    tentativa = None
    questao_obj = None

    if request.method == 'POST':
        logger.info(f"Iniciando avaliação discursiva para o usuário: {request.user.username}")
        
        user_answer = request.POST.get('user_answer', '').strip()
        line_count_str = request.POST.get('line_count', '0').strip()
        questao_id = request.POST.get('questao_id')
        submitted_user_answer = user_answer

        # Validações iniciais
        if not service_initialized or not service:
            evaluation_error = "O serviço de IA não pôde ser inicializado. Verifique as configurações."
        elif not user_answer:
            evaluation_error = "A resposta enviada está vazia. Por favor, escreva sua resposta antes de submeter."
        elif not questao_id:
            evaluation_error = "O identificador da questão original não foi encontrado."
        else:
            try:
                # 1. Recupera a questão original
                questao_obj = get_object_or_404(Questao, id=questao_id, tipo='DISC')
                submitted_exam_context = questao_obj.enunciado
                
                # 2. Processa o enunciado para evitar "blocão" na tela de resultado
                # Isso separa Contexto, Comando e Alíneas para o loop no HTML
                questao_original_data = parse_discursive_question(submitted_exam_context)

                # 3. Salva ou atualiza a tentativa do usuário no banco de dados
                tentativa, _ = TentativaResposta.objects.update_or_create(
                    usuario=request.user, 
                    questao=questao_obj,
                    defaults={
                        'resposta_discursiva': user_answer, 
                        'data_resposta': timezone.now()
                    }
                )

                # 4. Trata a contagem de linhas para a fórmula (NPD = NC - 2*NE/TL)
                try:
                    line_count_int = int(line_count_str) if line_count_str else 0
                except ValueError:
                    line_count_int = 0

                # 5. Chama o serviço de IA para gerar a avaliação detalhada
                logger.info(f"Chamando IA para avaliar QID={questao_id}. Linhas informadas: {line_count_int}")
                evaluation_result_text = service.evaluate_discursive_answer(
                    exam_context=submitted_exam_context, 
                    user_answer=user_answer, 
                    line_count=line_count_int
                )

                if evaluation_result_text:
                    # 6. Realiza o parsing do texto bruto retornado pela IA
                    parsed_scores = parse_evaluation_scores(evaluation_result_text)
                    
                    # 7. Registra a avaliação no banco de dados
                    # CORREÇÃO: Chave 'Justificativa_NC' para bater com o parser no utils.py
                    Avaliacao.objects.update_or_create(
                        tentativa=tentativa,
                        defaults={
                            'nc': parsed_scores.get('NC'),
                            'ne': parsed_scores.get('NE'),
                            'npd': parsed_scores.get('NPD'),
                            'feedback_ai': evaluation_result_text,
                            'justificativa_nc_ai': parsed_scores.get('Justificativa_NC'),
                            'comentarios_ai': parsed_scores.get('Comentários'),
                        }
                    )
                    messages.success(request, "Sua resposta foi avaliada com sucesso pela IA!")
                else:
                    evaluation_error = "A IA não retornou um resultado de avaliação válido. Tente novamente em instantes."

            except Exception as e:
                logger.error(f"Erro crítico em evaluate_discursive_answer_view: {str(e)}", exc_info=True)
                evaluation_error = f"Ocorreu um erro ao processar sua avaliação: {str(e)}"

    elif request.method == 'GET':
        # Se tentar acessar via GET, redireciona para a página de geração
        return redirect('generator:generate_discursive_exam')

    # Atualiza o contexto final para o render
    context.update({
        'evaluation_result_text': evaluation_result_text,
        'evaluation_error': evaluation_error,
        'submitted_exam_context': submitted_exam_context,
        'submitted_user_answer': submitted_user_answer,
        'questao_original_data': questao_original_data, # Passa os dados estruturados (Alíneas)
        'parsed_scores': parsed_scores,
        'tentativa': tentativa,
        'questao': questao_obj,
    })
    
    return render(request, 'generator/discursive_evaluation_result.html', context)

@login_required
def configurar_simulado_view(request):
    context, _, _ = _get_base_context_and_service()
    form = SimuladoConfigForm(request.POST or None)
    context['form'] = form

    if request.method == 'POST':
        if form.is_valid():
            num_ce = form.cleaned_data.get('num_ce')
            area_obj = form.cleaned_data.get('area')
            dificuldade_ce = form.cleaned_data.get('dificuldade_ce')
            topico_filtro = form.cleaned_data.get('topico', '').strip()
            area_nome_log = area_obj.nome if area_obj else 'Todas'
            dif_log = dificuldade_ce or 'Qualquer'
            top_log = topico_filtro or 'Qualquer'
            logger.info(f"Configurando simulado C/E para {request.user.username}: Num={num_ce}, Area='{area_nome_log}', Dif='{dif_log}', Tópico='{top_log}'")

            try:
                ce_queryset = Questao.objects.filter(tipo='CE')
                if area_obj:
                    # CORRIGIDO: 'area' -> 'topico__area_conhecimento'
                    ce_queryset = ce_queryset.filter(topico__area_conhecimento=area_obj)
                if dificuldade_ce:
                    ce_queryset = ce_queryset.filter(dificuldade=dificuldade_ce)
                if topico_filtro:
                    # CORRIGIDO: 'texto_comando' -> 'enunciado'
                    ce_queryset = ce_queryset.filter(
                        Q(topico__nome__icontains=topico_filtro) |
                        Q(enunciado__icontains=topico_filtro) |
                        Q(texto_motivador__icontains=topico_filtro)
                    )
                
                selected_ids = list(ce_queryset.order_by('?').values_list('id', flat=True)[:num_ce])

                if not selected_ids:
                    messages.error(request, "Nenhuma questão C/E encontrada com os critérios selecionados.")
                    logger.warning(f"Nenhuma questão encontrada para simulado de {request.user.username} com filtros.")
                    return render(request, 'generator/configurar_simulado.html', context)

                if len(selected_ids) < num_ce:
                    messages.warning(request, f"Aviso: Apenas {len(selected_ids)} de {num_ce} questões C/E pedidas foram encontradas.")
                
                request.session['simulado_config'] = {
                    'num_ce': len(selected_ids),
                    'area_id': area_obj.id if area_obj else None,
                    'area_nome': area_obj.nome if area_obj else 'Todas',
                    'dificuldade_ce': dificuldade_ce,
                    'topico_filtro': topico_filtro,
                }
                request.session['simulado_questao_ids'] = selected_ids
                request.session['simulado_indice_atual'] = 0
                logger.info(f"Simulado C/E configurado para {request.user.username}. IDs: {selected_ids}. Redirecionando...")
                messages.success(request, f"Simulado com {len(selected_ids)} questões C/E pronto para começar!")
                return redirect('generator:realizar_simulado')
            except Exception as e:
                logger.error(f"Erro ao selecionar questões C/E para o simulado: {e}", exc_info=True)
                messages.error(request, "Ocorreu um erro inesperado ao preparar o simulado.")
                return render(request, 'generator/configurar_simulado.html', context)
        else:
            logger.warning(f"Formulário de configuração de simulado inválido: {form.errors.as_json()}")
    
    return render(request, 'generator/configurar_simulado.html', context)


@login_required
def realizar_simulado_view(request):
    context, _, _ = _get_base_context_and_service()
    questao_ids = request.session.get('simulado_questao_ids', [])
    indice_atual = request.session.get('simulado_indice_atual', 0)

    if request.method == 'POST':
        resposta_submetida = request.POST.get('resposta_simulado')
        questao_id_respondida = request.POST.get('questao_id')
        
        if not questao_id_respondida or resposta_submetida is None:
            messages.warning(request, "Resposta ou ID da questão ausente. Tente novamente.")
            return redirect('generator:realizar_simulado')
        if not questao_ids:
            messages.error(request, "Erro: Configuração do simulado não encontrada na sessão.")
            return redirect('generator:configurar_simulado')

        try:
            if indice_atual >= len(questao_ids) or int(questao_id_respondida) != questao_ids[indice_atual]:
                messages.error(request, "Erro de sequência no simulado ou simulado já finalizado.")
                request.session.pop('simulado_questao_ids', None)
                request.session.pop('simulado_indice_atual', None)
                request.session.pop('simulado_config', None)
                return redirect('generator:configurar_simulado')

            questao_obj = Questao.objects.get(id=questao_id_respondida)
            resposta_ce_valida = resposta_submetida.strip().upper()
            if questao_obj.tipo != 'CE' or resposta_ce_valida not in ['C', 'E']:
                messages.error(request, f"Resposta inválida ('{resposta_submetida}') para questão C/E.")
                return redirect('generator:realizar_simulado')
            
            tentativa, t_created = TentativaResposta.objects.update_or_create(
                usuario=request.user, questao=questao_obj,
                defaults={'resposta_ce': resposta_ce_valida, 'data_resposta': timezone.now()}
            )
            is_correct = (tentativa.resposta_ce == questao_obj.gabarito_ce)
            score = 1 if is_correct else -1
            Avaliacao.objects.update_or_create(
                tentativa=tentativa, defaults={'correto_ce': is_correct, 'score_ce': score}
            )
            
            indice_proxima = indice_atual + 1
            request.session['simulado_indice_atual'] = indice_proxima
            logger.info(f"Usuário {request.user.username} respondeu índice {indice_atual} (Q ID {questao_id_respondida}), avançando para índice {indice_proxima}.")

        except Questao.DoesNotExist:
            messages.error(request, "Erro: A questão respondida não foi encontrada.")
            request.session.pop('simulado_questao_ids', None); request.session.pop('simulado_indice_atual', None)
            return redirect('generator:configurar_simulado')
        except (IndexError, ValueError) as e:
            messages.error(request, f"Erro de índice no simulado: {e}")
            request.session.pop('simulado_questao_ids', None); request.session.pop('simulado_indice_atual', None)
            return redirect('generator:configurar_simulado')
        except Exception as e:
            logger.error(f"Erro inesperado ao salvar tentativa/avaliação do simulado: {e}", exc_info=True)
            messages.error(request, "Ocorreu um erro ao salvar sua resposta. Tente novamente.")
            return redirect('generator:realizar_simulado')
        
        return redirect('generator:realizar_simulado')

    if not questao_ids:
        messages.warning(request, "Simulado não iniciado ou configuração perdida. Por favor, configure novamente.")
        return redirect('generator:configurar_simulado')
    
    if indice_atual >= len(questao_ids):
        messages.success(request, "Simulado concluído!")
        simulado_finalizado_ids = request.session.pop('simulado_questao_ids', [])
        request.session['finalizado_simulado_questao_ids'] = simulado_finalizado_ids
        request.session.pop('simulado_indice_atual', None)
        logger.info(f"Simulado finalizado para {request.user.username}. IDs: {simulado_finalizado_ids}. Redirecionando...")
        return redirect('generator:resultado_simulado')
    
    questao_id_atual = questao_ids[indice_atual]
    try:
        # CORRIGIDO: 'area' -> 'topico__area_conhecimento'
        questao_atual = Questao.objects.select_related('topico__area_conhecimento').get(id=questao_id_atual)
        context['questao'] = questao_atual
        context['indice_atual'] = indice_atual + 1
        context['total_questoes'] = len(questao_ids)
        context['simulado_config'] = request.session.get('simulado_config', {})
        logger.info(f"Exibindo questão índice {indice_atual} (ID: {questao_id_atual}) para {request.user.username}. Total: {len(questao_ids)}")
    except Questao.DoesNotExist:
        messages.error(request, f"Erro: A questão {indice_atual + 1} do simulado (ID: {questao_id_atual}) não foi encontrada.")
        request.session.pop('simulado_questao_ids', None); request.session.pop('simulado_indice_atual', None)
        return redirect('generator:configurar_simulado')
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar questão {questao_id_atual} para o simulado: {e}", exc_info=True)
        messages.error(request, "Ocorreu um erro ao carregar a próxima questão do simulado.")
        return redirect('generator:configurar_simulado')
    
    return render(request, 'generator/realizar_simulado.html', context)


@login_required
def resultado_simulado_view(request):
    context, _, _ = _get_base_context_and_service()
    questao_ids = request.session.get('finalizado_simulado_questao_ids', [])
    simulado_config = request.session.get('simulado_config', {})
    request.session.pop('finalizado_simulado_questao_ids', None)

    if not questao_ids:
        messages.warning(request, "Não há resultados de simulado para exibir ou a sessão expirou.")
        return redirect('generator:dashboard')

    logger.info(f"Exibindo resultado do simulado para {request.user.username}. Questões IDs: {questao_ids}")
    tentativas_do_simulado = []
    stats_simulado = {}

    try:
        # CORRIGIDO: 'questao__area' -> 'questao__topico__area_conhecimento'
        tentativas_do_simulado = TentativaResposta.objects.filter(
            usuario=request.user, questao_id__in=questao_ids
        ).select_related(
            'questao', 'questao__topico__area_conhecimento'
        ).prefetch_related('avaliacao').order_by('data_resposta')
        
        total_respondidas = tentativas_do_simulado.count()
        acertos_ce = sum(1 for t in tentativas_do_simulado if hasattr(t, 'avaliacao') and t.avaliacao.correto_ce)
        erros_ce = total_respondidas - acertos_ce
        
        score_ce = acertos_ce - erros_ce
        percentual_ce = round((acertos_ce / total_respondidas) * 100) if total_respondidas > 0 else 0

        stats_simulado = {
            'total_questoes_planejado': simulado_config.get('num_ce', len(questao_ids)),
            'total_respondidas': total_respondidas,
            'acertos_ce': acertos_ce,
            'erros_ce': erros_ce,
            'score_ce': score_ce,
            'percentual_ce': percentual_ce,
            'config': simulado_config
        }
        logger.info(f"Stats do Simulado para {request.user.username}: {stats_simulado}")

        if total_respondidas < len(questao_ids):
            messages.warning(request, f"Atenção: Você respondeu {total_respondidas} de {len(questao_ids)} questões planejadas.")
    except Exception as e:
        logger.error(f"Erro ao buscar/calcular resultado do simulado: {e}", exc_info=True)
        messages.error(request, "Ocorreu um erro ao carregar os resultados detalhados do simulado.")
        stats_simulado = {'config': simulado_config}

    context['tentativas_simulado'] = tentativas_do_simulado
    context['stats_simulado'] = stats_simulado
    return render(request, 'generator/resultado_simulado.html', context)

@login_required
def area_list_view(request):
    context, _, _ = _get_base_context_and_service()
    try:
        areas = AreaConhecimento.objects.all().order_by('nome')
        context['areas'] = areas
    except Exception as e:
        logger.error(f"Erro ao listar Áreas de Conhecimento: {e}", exc_info=True)
        messages.error(request, "Erro ao carregar a lista de áreas.")
        context['areas'] = []
    
    return render(request, 'generator/area_list.html', context)

@login_required
@require_POST
def add_area_quick_from_generator_view(request):
    form = AreaConhecimentoForm(request.POST)
    if form.is_valid():
        try:
            form.save()
            nome_area = form.cleaned_data.get('nome')
            messages.success(request, f"Área '{nome_area}' adicionada com sucesso!")
            logger.info(f"Área rápida adicionada (via Gerador C/E): '{nome_area}' por {request.user.username}")
        except Exception as e:
            nome_area_tentativa = form.cleaned_data.get('nome', '[N/A]')
            logger.error(f"Erro ao salvar área rápida (via Gerador C/E) '{nome_area_tentativa}': {e}", exc_info=True)
            messages.error(request, f"Ocorreu um erro inesperado ao tentar salvar a área '{nome_area_tentativa}'.")
    else:
        error_list = [f"{field}: {error[0]}" for field, error in form.errors.items()]
        erro_msg = "Erro ao adicionar área: " + (error_list[0] if error_list else "Verifique os dados.")
        logger.warning(f"Tentativa inválida de adicionar Área Rápida (via Gerador C/E) por {request.user.username}: {form.errors.as_json()}")
        messages.error(request, erro_msg)

    return redirect('generator:generate_questions')

@login_required
def listar_questoes_ce_view(request):
    context = {}
    questoes_list = None
    is_filtered_list = False
    main_motivador = None
    id_list_str = request.GET.get('ids')
    query_filter_param = request.GET.get('q', '').strip()
    area_filter_params_str = request.GET.getlist('area')

    if id_list_str:
        logger.info(f"Listando por IDs específicos: [{id_list_str}]")
        try:
            id_list = [int(id_val.strip()) for id_val in id_list_str.split(',') if id_val.strip().isdigit()]
            if id_list:
                # CORRIGIDO: 'area' -> 'topico__area_conhecimento'
                questoes_list = Questao.objects.filter(id__in=id_list).select_related('topico__area_conhecimento', 'criado_por').order_by('id')
                is_filtered_list = True
                context['id_filter_param'] = id_list_str
                first_q = questoes_list.first()
                if first_q:
                    main_motivador = first_q.texto_motivador
            else:
                messages.warning(request, "IDs fornecidos para filtro são inválidos.")
        except (ValueError, TypeError) as e:
            logger.error(f"Erro ao converter IDs da lista: {e}")
            messages.error(request, "Erro ao processar IDs para filtro.")
    
    if questoes_list is None:
        # CORRIGIDO: 'area' -> 'topico__area_conhecimento'
        base_queryset = Questao.objects.filter(tipo='CE').select_related('topico__area_conhecimento', 'criado_por')

        if query_filter_param:
            # CORRIGIDO: 'texto_comando' -> 'enunciado'
            base_queryset = base_queryset.filter(
                Q(enunciado__icontains=query_filter_param) |
                Q(texto_motivador__icontains=query_filter_param) |
                Q(id__icontains=query_filter_param)
            )
            is_filtered_list = True
        
        valid_area_ids = [int(id_str) for id_str in area_filter_params_str if id_str.strip().isdigit()]
        if valid_area_ids:
            # CORRIGIDO: 'area_id__in' -> 'topico__area_conhecimento_id__in'
            base_queryset = base_queryset.filter(topico__area_conhecimento_id__in=valid_area_ids)
            is_filtered_list = True
            
        questoes_list = base_queryset.order_by('-criado_em')
        main_motivador = None

    items_per_page = getattr(settings, 'ITEMS_PER_PAGE_QUESTOES_CE', 20)
    paginator = Paginator(questoes_list or [], items_per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context['page_obj'] = page_obj
    context['paginator'] = paginator
    context['is_filtered_list'] = is_filtered_list
    context['main_motivador'] = main_motivador
    context['id_filter_param'] = id_list_str
    context['query_filter_param'] = query_filter_param
    context['area_filter_param'] = area_filter_params_str
    context['all_areas'] = AreaConhecimento.objects.all().order_by('nome')
    
    logger.info(f"Renderizando lista C/E. Filtrada: {is_filtered_list}. Página: {page_obj.number if page_obj else 'N/A'}")
    return render(request, 'generator/questions_ce.html', context)

@login_required
def listar_questoes_discursivas_view(request):
    context = {}
    query_filter_param = request.GET.get('q', '').strip()
    area_filter_param = request.GET.get('area', '')

    # CORRIGIDO: 'area' -> 'topico__area_conhecimento'
    questoes_list = Questao.objects.filter(tipo='DISC').select_related('topico__area_conhecimento', 'criado_por')

    if query_filter_param:
        # CORRIGIDO: 'texto_comando' -> 'enunciado'
        questoes_list = questoes_list.filter(Q(enunciado__icontains=query_filter_param) | Q(id__icontains=query_filter_param))
    
    if area_filter_param and area_filter_param.isdigit():
        try:
            # CORRIGIDO: 'area_id' -> 'topico__area_conhecimento_id'
            questoes_list = questoes_list.filter(topico__area_conhecimento_id=int(area_filter_param))
        except ValueError:
            messages.warning(request, f"ID Área inválido: {area_filter_param}")
    
    questoes_list = questoes_list.order_by('-criado_em')
    items_per_page = 20
    paginator = Paginator(questoes_list, items_per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context['page_obj'] = page_obj
    context['paginator'] = paginator
    context['is_filtered_list'] = bool(query_filter_param or (area_filter_param and area_filter_param.isdigit()))
    context['query_filter_param'] = query_filter_param
    context['area_filter_param'] = area_filter_param
    try:
        context['all_areas'] = AreaConhecimento.objects.all().order_by('nome')
    except Exception as e_area:
        logger.error(f"Erro buscar áreas: {e_area}")
        context['all_areas'] = None

    logger.info(f"Renderizando lista DISCURSIVAS. Filtrada: {context['is_filtered_list']}. Página: {page_obj.number}/{paginator.num_pages}")
    return render(request, 'generator/questions_discursivas.html', context)

@login_required
def listar_questoes_me_view(request):
    context = {}
    query_filter_param = request.GET.get('q', '').strip()
    area_filter_param = request.GET.get('area', '')

    questoes_list = Questao.objects.filter(tipo='ME').select_related('topico__area_conhecimento', 'criado_por')

    if query_filter_param:
        questoes_list = questoes_list.filter(
            Q(enunciado__icontains=query_filter_param) |
            Q(texto_motivador__icontains=query_filter_param) |
            Q(id__icontains=query_filter_param)
        )

    if area_filter_param and area_filter_param.isdigit():
        try:
            questoes_list = questoes_list.filter(topico__area_conhecimento_id=int(area_filter_param))
        except ValueError:
            messages.warning(request, f"ID Área inválido: {area_filter_param}")

    questoes_list = questoes_list.order_by('-criado_em')
    paginator = Paginator(questoes_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context['page_obj'] = page_obj
    context['paginator'] = paginator
    context['is_filtered_list'] = bool(query_filter_param or (area_filter_param and area_filter_param.isdigit()))
    context['query_filter_param'] = query_filter_param
    context['area_filter_param'] = area_filter_param
    context['all_areas'] = AreaConhecimento.objects.all().order_by('nome')

    return render(request, 'generator/questions_me.html', context)

