import logging
from django.contrib import messages
from venv import logger
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.urls import reverse
from django.db.models import Q
from generator.exceptions import AIResponseError, AIServiceError, ConfigurationError, GeneratorError, ParsingError
from generator.forms import AreaConhecimentoForm, DiscursiveExamForm, QuestionGeneratorForm, SimuladoConfigForm
from generator.models import AreaConhecimento, Avaliacao, Questao, TentativaResposta
from django.utils import timezone
import json
from venv import logger
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from generator.models import Avaliacao, Questao, TentativaResposta
from generator.utils import parse_evaluation_scores
from generator.views.views_functions import extrair_texto_completo_pdf
from generator.views.views_service_context import _get_base_context_and_service
# # --- Sua função _get_base_context_and_service ---

@login_required
def generate_questions_view(request):
    base_context, service, service_initialized = _get_base_context_and_service() # Garanta que esta função esteja definida ou importada
    context = base_context.copy()
    context['service_initialized'] = service_initialized

    max_q = getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 150)

    # Inicializa form para GET e como base para POST com erros
    form_instance = QuestionGeneratorForm(max_questions=max_q)
    context['page_obj'] = None
    # context['paginator'] = None # A variável 'paginator' local será criada depois, se necessário.
                                # No contexto, ela será adicionada se a paginação ocorrer.
    context['main_motivador'] = None

    if request.method == 'POST':
        # logger.info(f"POST generate_questions_view por {request.user.username}") # Certifique-se que 'logger' está definido
        request.session.pop('latest_ce_ids', None)
        request.session.pop('latest_ce_motivador', None)

        form_instance = QuestionGeneratorForm(request.POST, request.FILES, max_questions=max_q)

        pdf_file_uploaded = False
        if 'pdf_contexto' in request.FILES and request.FILES.get('pdf_contexto'):
            pdf_file_uploaded = True
            # logger.info(f"Arquivo PDF '{request.FILES['pdf_contexto'].name}' foi detectado no POST.")

        if pdf_file_uploaded:
            if 'topic' in form_instance.fields:
                form_instance.fields['topic'].required = False
                # logger.info("Campo 'topic' tornado NÃO obrigatório porque um PDF foi enviado.")
        else:
            if 'topic' in form_instance.fields:
                form_instance.fields['topic'].required = True
                # logger.info("Nenhum PDF enviado, campo 'topic' permanece/torna-se obrigatório.")

        context['form'] = form_instance

        if form_instance.is_valid():
            # logger.info("Formulário de Geração C/E é VÁLIDO.")
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
                    contexto_para_ia = extrair_texto_completo_pdf(pdf_file_cleaned) # Garanta que esta função esteja definida ou importada
                    fonte_contexto = f"PDF: {pdf_file_cleaned.name}"

                    if not contexto_para_ia.strip():
                        messages.error(request, f"Não foi possível extrair conteúdo textual útil do PDF '{pdf_file_cleaned.name}'. O arquivo pode ser uma imagem, estar protegido, ser muito complexo ou estar vazio. Tente o contexto textual.")
                        return render(request, 'generator/question_generator.html', context)
                    # logger.info(f"Contexto para IA obtido do PDF: '{pdf_file_cleaned.name}' ({len(contexto_para_ia)} caracteres). Início: '{contexto_para_ia[:250]}...'")

                except ValueError as ve:
                    messages.error(request, str(ve)) # Erro vindo da função de extração
                    return render(request, 'generator/question_generator.html', context)
                except Exception as e_pdf_extract:
                    # logger.error(f"Erro crítico ao extrair texto do PDF '{pdf_file_cleaned.name}': {e_pdf_extract}", exc_info=True)
                    messages.error(request, "Ocorreu um erro inesperado ao tentar ler o arquivo PDF.")
                    return render(request, 'generator/question_generator.html', context)
            elif topic_text_cleaned:
                contexto_para_ia = topic_text_cleaned
                fonte_contexto = "Tópico Textual"
                # logger.info(f"Usando contexto do campo Tópico ({len(contexto_para_ia)} caracteres). Início: '{contexto_para_ia[:250]}...'")

            if not contexto_para_ia.strip(): # Checagem final do contexto antes de enviar para IA
                messages.error(request, "Contexto para IA está vazio. Forneça um tópico ou PDF com conteúdo legível.")
                return render(request, 'generator/question_generator.html', context)

            # logger.info(f"Preparando para chamar IA. Fonte: {fonte_contexto}. Num Questões: {num_questions}. Dificuldade: {difficulty}.")
            try:
                main_motivador, generated_items_data = service.generate_questions(
                    topic=contexto_para_ia,
                    num_questions=num_questions,
                    difficulty_level=difficulty
                )
                if not generated_items_data or not isinstance(generated_items_data, list):
                    messages.warning(request,"IA retornou dados inválidos."); generated_items_data = []
                saved_question_ids = []
                if generated_items_data:
                    # logger.info(f"Salvando {len(generated_items_data)} itens...")
                    for item_data in generated_items_data:
                        try:
                            if not isinstance(item_data, dict): continue
                            gabarito = item_data.get('gabarito'); afirmacao = item_data.get('afirmacao')
                            if not gabarito or gabarito not in ['C', 'E'] or not afirmacao or not afirmacao.strip(): continue
                            q = Questao(tipo='CE', texto_motivador=main_motivador, texto_comando=afirmacao, gabarito_ce=gabarito, justificativa_gabarito=item_data.get('justificativa'), dificuldade=(difficulty or 'medio'), area=area_obj, criado_por=request.user)
                            q.save(); saved_question_ids.append(q.id)
                        except Exception as save_error: pass # logger.error(f"Erro salvar C/E item: {save_error}", exc_info=True)
                if saved_question_ids:
                    messages.success(request, f"{len(saved_question_ids)} questões C/E geradas!")
                    request.session['latest_ce_ids'] = saved_question_ids
                    request.session['latest_ce_motivador'] = main_motivador if main_motivador else ""
                else:
                    if generated_items_data: messages.warning(request,"Nenhuma questão válida foi salva (verifique formato/dados da IA).")
                    else: messages.warning(request,"IA não retornou questões válidas para salvar.")
                if generated_items_data and len(saved_question_ids) < len(generated_items_data):
                    messages.warning(request,"Alguns itens podem não ter sido salvos.")

                return redirect(reverse('generator:generate_questions'))

            except Exception as e:
                # logger.error(f"Erro INESPERADO na Geração ou Salvamento C/E: {e}", exc_info=True)
                context['error_message'] = f"Erro inesperado: {e}"
                messages.error(request, context['error_message']) # Adicionado para mostrar o erro ao usuário
                return render(request, 'generator/question_generator.html', context)
        else:
            # logger.warning(f"Formulário de Geração C/E INVÁLIDO: {form_instance.errors.as_json()}")
            messages.error(request, "Por favor, corrija os erros indicados no formulário.")
            # Não precisa renderizar aqui se o form inválido já é tratado pelo render no final da view POST
            # No entanto, é comum ter um render aqui para clareza.
            return render(request, 'generator/question_generator.html', context)

    # --- Lógica GET ---
    else:
        form_instance = QuestionGeneratorForm(max_questions=max_q) # Recria o form para GET
        context['form'] = form_instance
        # As inicializações de page_obj, paginator, main_motivador já foram feitas no início.

        # logger.debug(f"GET generate_questions_view por {request.user.username}")
        if request.GET.get('action') == 'clear':
            # logger.info("Limpando sessão 'latest_ce' via action=clear.")
            request.session.pop('latest_ce_ids', None)
            request.session.pop('latest_ce_motivador', None)
            messages.info(request, "Resultado anterior limpo.")
            return redirect(reverse('generator:generate_questions'))

        latest_ids = request.session.get('latest_ce_ids')
        context['main_motivador'] = request.session.get('latest_ce_motivador')
        
        # Limpa page_obj e paginator do contexto para garantir que não venham de um estado anterior se latest_ids não existir
        context['page_obj'] = None
        context['paginator'] = None # Especificamente para a chave do contexto

        if latest_ids:
            # logger.info(f"GET: IDs encontrados na sessão para paginação: {latest_ids}.")
            try:
                question_list = Questao.objects.filter(id__in=latest_ids).select_related('area', 'criado_por').order_by('id')
                # logger.info(f"GET: Número de questões encontradas no DB: {question_list.count()}")

                if question_list.exists():
                    items_per_page = getattr(settings, 'ITEMS_PER_PAGE_GENERATOR', 20)
                    
                    # ----- ALTERAÇÃO APLICADA AQUI -----
                    # Usar Paginator (com 'P' maiúsculo) para instanciar a classe
                    paginator_instance = Paginator(question_list, items_per_page)
                    # ------------------------------------
                    
                    # logger.info(f"GET: Paginator. Total de itens: {paginator_instance.count}, Total de páginas: {paginator_instance.num_pages}")

                    page_number = request.GET.get('page')
                    try:
                        page_obj = paginator_instance.get_page(page_number)
                    except PageNotAnInteger:
                        page_obj = paginator_instance.get_page(1)
                    except EmptyPage:
                        page_obj = paginator_instance.get_page(paginator_instance.num_pages)
                    
                    context['page_obj'] = page_obj
                    context['paginator'] = paginator_instance # Adiciona a instância ao contexto
                    
                    # logger.info(f"GET: Paginação configurada. Página: {page_obj.number} de {paginator_instance.num_pages}.")
                else:
                    # logger.warning(f"GET: IDs {latest_ids} na sessão, mas NENHUMA questão encontrada. Limpando sessão.")
                    request.session.pop('latest_ce_ids', None); request.session.pop('latest_ce_motivador', None)
                    context['main_motivador'] = None
            except Exception as e:
                # logger.error(f"GET: Erro ao buscar/paginar questões da sessão: {e}", exc_info=True)
                messages.error(request, "Erro ao carregar ou paginar as questões da sessão.")
                request.session.pop('latest_ce_ids', None); request.session.pop('latest_ce_motivador', None)
                context['main_motivador'] = None
        else:
            # logger.info("GET: Nenhum 'latest_ce_ids' encontrado na sessão.")
            # As chaves 'main_motivador', 'page_obj', 'paginator' já foram setadas como None ou serão se não houver latest_ids.
            pass # Não é necessário fazer nada aqui, o contexto já está como None para esses itens.
        
    return render(request, 'generator/question_generator.html', context)

@login_required
def generate_discursive_exam_view(request):
    base_context, service, service_initialized = _get_base_context_and_service()
    context = base_context.copy() # Inicia com o contexto base (que deve ter 'all_areas')
    context['service_initialized'] = service_initialized
    
    discursive_exam_text = None
    questao_id = None
    # context['error_message'] já vem de base_context, se houver

    if request.method == 'POST':
        form = DiscursiveExamForm(request.POST) # Seu DiscursiveExamForm
        if form.is_valid():
            if not service_initialized or not service:
                messages.error(request, context.get('error_message', "Serviço de IA indisponível para processar."))
                context['form'] = form 
                return render(request, 'generator/discursive_exam_generator.html', context)

            base_topic_or_context = form.cleaned_data.get('base_topic_or_context')
            num_aspects = form.cleaned_data.get('num_aspects', 3)
            area_obj = form.cleaned_data.get('area')
            
            # Obter difficulty_level do formulário validado
            difficulty = form.cleaned_data.get('difficulty_level', 'medio') # Use o default do seu form se houver
            
            # 'complexity' é o nome do parâmetro esperado pelo seu service.generate_discursive_exam_question
            complexity_for_service = difficulty 
            language = 'pt-br' # Defina ou pegue do form se necessário

            current_user = request.user if request.user.is_authenticated else None
            
            logger.info(f"POST Gerador Discursiva: Tópico='{base_topic_or_context[:50]}...', Aspectos={num_aspects}, Área={area_obj}, Dificuldade={complexity_for_service}")

            try:
                discursive_exam_text = service.generate_discursive_exam_question(
                    base_topic_or_context=base_topic_or_context, 
                    num_aspects=num_aspects, 
                    area=area_obj.nome if area_obj else None, 
                    complexity=complexity_for_service, 
                    language=language
                )
                
                if discursive_exam_text and isinstance(discursive_exam_text, str) and discursive_exam_text.strip():
                    try:
                        q = Questao(
                            tipo='DISC',
                            texto_comando=discursive_exam_text,
                            aspectos_discursiva=f"Avaliar {num_aspects} aspecto(s) solicitado(s).",
                            dificuldade=difficulty, # Salva a dificuldade selecionada
                            area=area_obj, 
                            criado_por=current_user
                        )
                        q.save()
                        questao_id = q.id
                        logger.info(f"Questão Discursiva ID {questao_id} salva com sucesso.")
                        messages.success(request, f"Questão discursiva (ID: {questao_id}) gerada com sucesso! Você pode respondê-la abaixo ou buscar por ela mais tarde.")
                        return redirect(f"{reverse('generator:generate_discursive_exam')}?questao_id={questao_id}")
                    except Exception as db_error:
                        logger.error(f"Erro ao salvar questão discursiva no banco de dados: {db_error}", exc_info=True)
                        messages.error(request, "Ocorreu um erro ao tentar salvar a questão discursiva gerada.")
                        questao_id = None 
                else:
                    messages.warning(request, "A IA não retornou um texto válido para a questão discursiva.")
                    discursive_exam_text = None 
                    questao_id = None
            # except (ParsingError, AIResponseError, etc.) as e: # Suas exceções específicas
            #     logger.error(f"Erro específico da IA ao gerar questão discursiva: {e}", exc_info=False)
            #     context['error_message'] = f"Falha na geração pela IA: {e}"
            #     discursive_exam_text = None; questao_id = None
            except Exception as e: 
                logger.error(f"Erro inesperado ao gerar questão discursiva: {e}", exc_info=True)
                context['error_message'] = f"Falha inesperada durante a geração da questão: {e}"
                discursive_exam_text = None; questao_id = None
        else: 
            logger.warning(f"Formulário Gerador Discursiva INVÁLIDO: {form.errors.as_json()}")
            messages.error(request, "Por favor, corrija os erros indicados no formulário.")
        
        context['form'] = form # Passa o form (com dados e/ou erros) para o contexto

    # --- Lógica GET ---
    else: # request.method == 'GET'
        form = DiscursiveExamForm() # Form vazio para nova geração
        
        questao_id_from_url = request.GET.get('questao_id')
        logger.debug(f"GET generate_discursive_exam por {request.user.username}. questao_id_from_url: {questao_id_from_url}")

        if questao_id_from_url and questao_id_from_url.isdigit():
            qid = int(questao_id_from_url)
            logger.info(f"Tentando carregar Questão Discursiva ID={qid} via GET.")
            try:
                # USA get_object_or_404 AGORA QUE ESTÁ IMPORTADO
                questao_para_exibir = get_object_or_404(Questao, id=qid, tipo='DISC')
                discursive_exam_text = questao_para_exibir.texto_comando
                questao_id = questao_para_exibir.id
                logger.info(f"Questão Discursiva ID {questao_id} carregada para exibição.")
                # Opcional: Preencher o form com os dados da questão carregada
                # form = DiscursiveExamForm(initial={
                #     'base_topic_or_context': questao_para_exibir.texto_comando_original_ou_topico,
                #     'num_aspects': ..., 
                #     'area': questao_para_exibir.area,
                #     'difficulty_level': questao_para_exibir.dificuldade 
                # })
            except Questao.DoesNotExist: # Erro mais específico se get_object_or_404 não for usado ou falhar por outro motivo
                 logger.warning(f"Questão discursiva ID {qid} não encontrada ou não é do tipo DISC.", exc_info=True)
                 messages.warning(request, f"A questão discursiva com ID {qid} não foi encontrada.")
                 discursive_exam_text = None; questao_id = None
            except Exception as e: 
                 logger.error(f"Erro ao buscar questão discursiva ID {qid} via GET: {e}", exc_info=True)
                 messages.error(request, f"Erro ao tentar carregar a questão discursiva com ID {qid}.")
                 discursive_exam_text = None; questao_id = None
        
        context['form'] = form # Adiciona o form (limpo ou com 'initial') ao contexto

    context['discursive_exam_text'] = discursive_exam_text
    context['questao_id'] = questao_id

    return render(request, 'generator/discursive_exam_generator.html', context)


# --- VIEW PARA AVALIAR RESPOSTA DISCURSIVA ---
@login_required
def evaluate_discursive_answer_view(request):
    context, service, service_initialized = _get_base_context_and_service()
    evaluation_result_text = None # Texto completo da IA
    evaluation_error = None # Mensagem de erro para o usuário
    submitted_exam_context = None # Comando da questão submetida
    submitted_user_answer = None # Resposta do usuário submetida
    parsed_scores = None # Dicionário com notas parseadas (NC, NE, NPD, etc.)
    tentativa = None # Objeto TentativaResposta salvo/atualizado
    questao_obj = None # Objeto Questao original

    context['error_message'] = context.get('error_message') # Pega erro inicial do serviço

    if request.method == 'POST':
        logger.info(f"POST evaluate_discursive_answer_view por {request.user.username}")
        user_answer = request.POST.get('user_answer', '').strip()
        # exam_context não é mais necessário buscar do POST se tivermos questao_id
        # exam_context = request.POST.get('exam_context', '').strip()
        line_count_str = request.POST.get('line_count', '0').strip()
        questao_id = request.POST.get('questao_id') # <<< Pega o ID da questão do form

        submitted_user_answer = user_answer # Guarda para reexibir no template

        # Validações Iniciais
        if not service_initialized or not service:
             logger.error(f"POST evaluate_discursive_answer_view sem serviço IA por {request.user.username}.")
             evaluation_error = context.get('error_message', "Serviço de IA indisponível no momento.")
        elif not user_answer:
             logger.warning(f"Avaliação discursiva sem resposta do usuário por {request.user.username}.")
             evaluation_error = "A resposta do usuário não pode estar vazia."
        elif not questao_id:
             logger.error(f"ID da questão não recebido no POST para avaliação discursiva por {request.user.username}.")
             evaluation_error = "Erro: ID da questão original não foi encontrado no envio."
        else:
            # Tenta buscar a questão e processar
            try:
                # Busca a Questão original no DB
                questao_obj = Questao.objects.get(id=questao_id, tipo='DISC') # Garante que é discursiva
                logger.info(f"Questão Discursiva ID {questao_id} encontrada para avaliação.")
                submitted_exam_context = questao_obj.texto_comando # Pega o comando original da questão

                # --- Cria ou Atualiza a Tentativa de Resposta ---
                tentativa, created_tentativa = TentativaResposta.objects.update_or_create(
                    usuario=request.user,
                    questao=questao_obj,
                    defaults={'resposta_discursiva': user_answer, 'data_resposta': timezone.now()}
                )
                log_msg_tentativa = "criada" if created_tentativa else "atualizada"
                logger.info(f"TentativaResposta ID {tentativa.id} {log_msg_tentativa} para Questao ID {questao_id}.")

                # --- Chama a IA para avaliar ---
                # Valida line_count
                try: line_count_int = int(line_count_str) if line_count_str else 0
                except ValueError: logger.warning(f"Valor de line_count inválido ('{line_count_str}'), usando 0."); line_count_int = 0

                logger.info(f"Dados enviados p/ IA avaliar: Contexto={len(submitted_exam_context)}, Resp={len(user_answer)}, Linhas={line_count_int}")
                try:
                    logger.info(">>> CHAMANDO service.evaluate_discursive_answer <<<")
                    evaluation_result_text = service.evaluate_discursive_answer(
                        exam_context=submitted_exam_context, # Passa o comando original da questão
                        user_answer=user_answer,
                        line_count=line_count_int # Passa o número de linhas (ou 0)
                    )
                    logger.info("Avaliação textual recebida do serviço IA.")
                    context['error_message'] = None # Limpa erro inicial se a chamada foi ok

                    # --- Tenta fazer o PARSE e Salvar/Atualizar Avaliação ---
                    if evaluation_result_text and isinstance(evaluation_result_text, str) and evaluation_result_text.strip():
                        try:
                            logger.info(">>> Tentando PARSE via utils.parse_evaluation_scores <<<")
                            parsed_scores = parse_evaluation_scores(evaluation_result_text) # Chama parser externo
                            logger.info(f">>> Resultado Parsing: {parsed_scores}")

                            # --- Salva/Atualiza a Avaliação no DB ---
                            # Garante que as chaves existem no dict parseado, usando .get() com default None
                            avaliacao_obj, created_avaliacao = Avaliacao.objects.update_or_create(
                                tentativa=tentativa, # Chave de busca (OneToOne)
                                defaults={ # Campos a serem atualizados ou criados
                                    'nc': parsed_scores.get('NC'),
                                    'ne': parsed_scores.get('NE'),
                                    'npd': parsed_scores.get('NPD'),
                                    'feedback_ai': evaluation_result_text, # Texto bruto completo da IA
                                    'justificativa_nc_ai': parsed_scores.get('Justificativa'),
                                    'comentarios_ai': parsed_scores.get('Comentários'),
                                    # data_avaliacao é auto_now_add ou auto_now, não precisa setar aqui
                                }
                            )
                            log_msg_avaliacao = "criada" if created_avaliacao else "atualizada"
                            logger.info(f"Avaliacao {log_msg_avaliacao} no DB para Tentativa ID {tentativa.id}.")
                            messages.success(request, "Sua resposta foi avaliada pela IA e salva!")
                            # --- Fim Salvamento Avaliação ---

                        except NameError:
                             logger.error("!!! FUNÇÃO 'parse_evaluation_scores' NÃO ENCONTRADA !!! Verifique imports em utils.py ou views.py.")
                             evaluation_error = "Erro interno crítico: Função de parsing de notas não encontrada."; parsed_scores = None
                             # Não salva Avaliacao se o parse falhar. Tentativa já foi salva.
                        except (ParsingError, ValueError, TypeError) as parse_error: # Pega erros de conversão também
                            logger.error(f"Erro PARSE/SAVE Avaliação Discursiva: {parse_error}", exc_info=True)
                            evaluation_error = f"Erro ao processar ou salvar o resultado da avaliação: {parse_error}. A avaliação da IA está disponível, mas as notas podem não ter sido salvas."; parsed_scores = None
                            # Salva a avaliação com o texto bruto, mas sem as notas parseadas
                            Avaliacao.objects.update_or_create(
                                tentativa=tentativa,
                                defaults={'feedback_ai': evaluation_result_text} # Salva pelo menos o texto
                            )
                        except Exception as db_save_error: # Outro erro ao salvar Avaliacao
                             logger.error(f"Erro DB ao salvar Avaliacao Discursiva: {db_save_error}", exc_info=True)
                             evaluation_error = "Erro ao salvar os detalhes da avaliação no banco de dados."; parsed_scores = None
                             Avaliacao.objects.update_or_create(
                                tentativa=tentativa,
                                defaults={'feedback_ai': evaluation_result_text} # Salva pelo menos o texto
                            )

                    else: # evaluation_result_text vazio ou inválido
                        logger.warning("Serviço IA retornou texto de avaliação vazio ou inválido, nada para parsear/salvar.")
                        evaluation_error = "A IA não retornou uma avaliação válida para esta resposta."
                        parsed_scores = None
                        # Salva a tentativa, mas cria uma avaliação vazia ou com erro
                        Avaliacao.objects.update_or_create(
                            tentativa=tentativa,
                            defaults={'feedback_ai': 'IA não retornou avaliação válida.'}
                        )
                # Fim do try da chamada da IA/Parsing/Save
                except (AIResponseError, AIServiceError, GeneratorError, ConfigurationError) as service_error:
                     logger.error(f"Erro ao chamar serviço de avaliação discursiva: {service_error}", exc_info=True)
                     evaluation_error = f"Erro na comunicação com o serviço de IA: {service_error}"; evaluation_result_text = None; parsed_scores = None
                     # Salva a tentativa, mas cria uma avaliação com erro
                     Avaliacao.objects.update_or_create(
                            tentativa=tentativa,
                            defaults={'feedback_ai': f'Erro ao chamar IA: {service_error}'}
                        )
                except Exception as call_error: # Outro erro na chamada
                     logger.error(f"Erro inesperado ao chamar serviço de avaliação: {call_error}", exc_info=True)
                     evaluation_error = f"Ocorreu um erro inesperado ao solicitar a avaliação: {call_error}"; evaluation_result_text = None; parsed_scores = None
                     Avaliacao.objects.update_or_create(
                            tentativa=tentativa,
                            defaults={'feedback_ai': f'Erro inesperado ao chamar IA: {call_error}'}
                        )

            # Fim do try de buscar questão
            except Questao.DoesNotExist:
                 logger.error(f"Questão DISC ID {questao_id} não encontrada no DB para avaliação por {request.user.username}.")
                 evaluation_error = "Erro: A questão original para esta avaliação não foi encontrada ou é inválida."
            except Exception as general_error: # Pega outros erros inesperados (ex: DB na busca da questão)
                 logger.error(f"Erro inesperado geral em evaluate_discursive_answer_view: {general_error}", exc_info=True)
                 evaluation_error = "Ocorreu um erro inesperado no servidor ao processar sua solicitação."

    # Fim do if request.method == 'POST'
    elif request.method == 'GET':
        # Se alguém acessar a URL de avaliação via GET, redireciona para um lugar mais útil
        logger.warning(f"Tentativa de acesso GET a evaluate_discursive_answer_view por {request.user.username or 'Anônimo'}")
        messages.info(request, "Para avaliar uma resposta discursiva, primeiro gere ou selecione uma questão.")
        # Redireciona para a geração de questão discursiva ou dashboard
        return redirect('generator:generate_discursive_exam')

    # Atualiza contexto final ANTES de renderizar (para POST)
    context['evaluation_result_text'] = evaluation_result_text # Texto completo da IA ou None
    context['evaluation_error'] = evaluation_error # Mensagem de erro ou None
    context['submitted_exam_context'] = submitted_exam_context # Comando da questão ou None
    context['submitted_user_answer'] = submitted_user_answer # Resposta do usuário ou None
    context['parsed_scores'] = parsed_scores # Dict com notas ou None
    context['tentativa'] = tentativa # Objeto TentativaResposta ou None (útil para links, etc.)
    context['questao'] = questao_obj # Objeto Questao ou None

    logger.debug(f"Contexto final (evaluate_discursive_answer_view): User={request.user.username}, TentativaID={tentativa.id if tentativa else None}, QuestaoID={questao_obj.id if questao_obj else None}, Error='{evaluation_error}', Parsed={parsed_scores is not None}")
    # Renderiza a página de resultado da avaliação
    return render(request, 'generator/discursive_evaluation_result.html', context)


# --- VISÃO Configuração do Simulado (COM FILTRO DE TÓPICO) ---
@login_required
def configurar_simulado_view(request):
    context, _, _ = _get_base_context_and_service()
    form = SimuladoConfigForm(request.POST or None)
    context['form'] = form # Adiciona o form ao contexto para GET e POST inválido

    if request.method == 'POST':
        if form.is_valid():
            num_ce = form.cleaned_data.get('num_ce')
            area_obj = form.cleaned_data.get('area') # Objeto AreaConhecimento ou None
            dificuldade_ce = form.cleaned_data.get('dificuldade_ce') # String ou None
            topico_filtro = form.cleaned_data.get('topico', '').strip() # String ou vazia

            area_nome_log = area_obj.nome if area_obj else 'Todas'
            dif_log = dificuldade_ce or 'Qualquer'
            top_log = topico_filtro or 'Qualquer'
            logger.info(f"Configurando simulado C/E para {request.user.username}: "
                        f"Num={num_ce}, Area='{area_nome_log}', Dif='{dif_log}', Tópico='{top_log}'")

            selected_ids = []
            try:
                # Filtros base C/E
                ce_queryset = Questao.objects.filter(tipo='CE')

                # Aplica filtros opcionais
                if area_obj:
                    ce_queryset = ce_queryset.filter(area=area_obj)
                if dificuldade_ce:
                    ce_queryset = ce_queryset.filter(dificuldade=dificuldade_ce)
                if topico_filtro:
                    # Busca no nome do tópico (se relacionado) OU no texto do comando/motivador
                    ce_queryset = ce_queryset.filter(
                        Q(topico__nome__icontains=topico_filtro) | # Assumindo relação 'topico' com 'nome'
                        Q(texto_comando__icontains=topico_filtro) |
                        Q(texto_motivador__icontains=topico_filtro)
                    )
                    logger.info(f"Filtrando questões por tópico/texto contendo: '{topico_filtro}'")

                # Seleciona aleatoriamente até o número desejado
                selected_ids = list(ce_queryset.order_by('?').values_list('id', flat=True)[:num_ce])

                if not selected_ids:
                    messages.error(request, "Nenhuma questão C/E encontrada com os critérios selecionados. Ajuste os filtros e tente novamente.")
                    logger.warning(f"Nenhuma questão encontrada para simulado de {request.user.username} com filtros: Area={area_nome_log}, Dif={dif_log}, Tópico={top_log}")
                    # Re-renderiza o form com a mensagem de erro
                    return render(request, 'generator/configurar_simulado.html', context)

                if len(selected_ids) < num_ce:
                    messages.warning(request, f"Aviso: Apenas {len(selected_ids)} questões C/E encontradas com os critérios selecionados (você pediu {num_ce}).")
                    logger.info(f"Encontradas {len(selected_ids)}/{num_ce} questões para simulado de {request.user.username}.")


                # Armazena na sessão (salvando os IDs, não os objetos)
                request.session['simulado_config'] = {
                    'num_ce': len(selected_ids), # Salva o número real de questões selecionadas
                    'area_id': area_obj.id if area_obj else None,
                    'area_nome': area_obj.nome if area_obj else 'Todas', # Guarda nome para exibição
                    'dificuldade_ce': dificuldade_ce,
                    'topico_filtro': topico_filtro,
                }
                request.session['simulado_questao_ids'] = selected_ids
                request.session['simulado_indice_atual'] = 0 # Começa no índice 0
                # request.session['simulado_respostas'] = {} # Não parece ser usado, pode remover se não for necessário

                logger.info(f"Simulado C/E configurado para {request.user.username}. Questões IDs: {selected_ids}. Redirecionando...")
                messages.success(request, f"Simulado com {len(selected_ids)} questões C/E pronto para começar!")
                return redirect('generator:realizar_simulado')

            except Exception as e:
                logger.error(f"Erro ao selecionar questões C/E para o simulado: {e}", exc_info=True)
                messages.error(request, "Ocorreu um erro inesperado ao preparar o simulado. Tente novamente.")
                # Re-renderiza o form
                return render(request, 'generator/configurar_simulado.html', context)
        else: # Form inválido
            logger.warning(f"Formulário de configuração de simulado inválido: {form.errors.as_json()}")
            # O template exibirá os erros do form

    # Para GET ou POST inválido
    return render(request, 'generator/configurar_simulado.html', context)

@login_required
def realizar_simulado_view(request):
    context, _, _ = _get_base_context_and_service()
    questao_ids = request.session.get('simulado_questao_ids', [])
    # Índice da questão a ser exibida/processada AGORA (começa em 0)
    indice_atual = request.session.get('simulado_indice_atual', 0)

    # --- Lógica para POST (Recebe resposta da questão anterior) ---
    if request.method == 'POST':
        resposta_submetida = request.POST.get('resposta_simulado') # Espera 'C' ou 'E'
        questao_id_respondida = request.POST.get('questao_id') # ID da questão que foi exibida

        # Validações básicas
        if not questao_id_respondida or resposta_submetida is None:
            messages.warning(request, "Resposta ou ID da questão ausente. Tente novamente.")
            logger.warning(f"POST realizar_simulado sem ID ({questao_id_respondida}) ou resposta ({resposta_submetida}) por {request.user.username}")
            # Recarrega a mesma questão para o usuário tentar de novo
            return redirect('generator:realizar_simulado')

        if not questao_ids:
             messages.error(request, "Erro: Configuração do simulado não encontrada na sessão.")
             logger.error(f"POST realizar_simulado sem 'simulado_questao_ids' na sessão por {request.user.username}")
             return redirect('generator:configurar_simulado')

        try:
            # Verifica se o ID respondido é o esperado para o índice atual
            # Isso previne submissões fora de ordem ou após o término
            if indice_atual >= len(questao_ids) or int(questao_id_respondida) != questao_ids[indice_atual]:
                 messages.error(request, "Erro de sequência no simulado ou simulado já finalizado. Reiniciando configuração.")
                 logger.error(f"Erro de sequência/índice em realizar_simulado por {request.user.username}. Índice sessão: {indice_atual}, ID recebido: {questao_id_respondida}, IDs sessão: {questao_ids}")
                 # Limpa sessão do simulado
                 request.session.pop('simulado_questao_ids', None)
                 request.session.pop('simulado_indice_atual', None)
                 request.session.pop('simulado_config', None)
                 return redirect('generator:configurar_simulado')

            # Busca o objeto Questao
            questao_obj = Questao.objects.get(id=questao_id_respondida)

            # Valida a resposta C/E
            resposta_ce_valida = resposta_submetida.strip().upper()
            if questao_obj.tipo != 'CE' or resposta_ce_valida not in ['C', 'E']:
                 messages.error(request, f"Resposta inválida ('{resposta_submetida}') para questão C/E.")
                 logger.warning(f"Resposta inválida '{resposta_submetida}' para Q ID {questao_id_respondida} por {request.user.username}")
                 return redirect('generator:realizar_simulado') # Recarrega questão atual

            # Salva/Atualiza TentativaResposta
            tentativa, t_created = TentativaResposta.objects.update_or_create(
                usuario=request.user,
                questao=questao_obj,
                defaults={'resposta_ce': resposta_ce_valida, 'data_resposta': timezone.now()}
            )
            logger.info(f"Tentativa ID {tentativa.id} {'criada' if t_created else 'atualizada'} p/ Q ID {questao_id_respondida} no simulado por {request.user.username}.")

            # Salva/Atualiza Avaliação C/E
            is_correct = (tentativa.resposta_ce == questao_obj.gabarito_ce)
            score = 1 if is_correct else -1
            avaliacao, a_created = Avaliacao.objects.update_or_create(
                tentativa=tentativa,
                defaults={'correto_ce': is_correct, 'score_ce': score}
            )
            logger.info(f"Avaliacao C/E {'criada' if a_created else 'atualizada'} p/ Tentativa ID {tentativa.id}. Correto: {is_correct}")

            # <<< CORREÇÃO: Incrementa o índice ATUAL da sessão para a PRÓXIMA questão >>>
            indice_proxima = indice_atual + 1
            request.session['simulado_indice_atual'] = indice_proxima
            logger.info(f"Usuário {request.user.username} respondeu índice {indice_atual} (Q ID {questao_id_respondida}), avançando para índice {indice_proxima}.")

        except Questao.DoesNotExist:
            messages.error(request, "Erro: A questão respondida não foi encontrada.")
            logger.error(f"Questão ID {questao_id_respondida} não encontrada no DB durante simulado por {request.user.username}")
            request.session.pop('simulado_questao_ids', None); request.session.pop('simulado_indice_atual', None)
            return redirect('generator:configurar_simulado')
        except IndexError: # Caso o índice calculado seja inválido (raro com a verificação acima)
            messages.error(request, "Erro: Índice inválido no simulado.")
            logger.error(f"IndexError em realizar_simulado por {request.user.username}. Índice: {indice_atual}, Total IDs: {len(questao_ids)}")
            request.session.pop('simulado_questao_ids', None); request.session.pop('simulado_indice_atual', None)
            return redirect('generator:configurar_simulado')
        except Exception as e:
            logger.error(f"Erro inesperado ao salvar tentativa/avaliação do simulado: {e}", exc_info=True)
            messages.error(request, "Ocorreu um erro ao salvar sua resposta. Tente novamente.")
            # Não avança o índice, recarrega a mesma questão
            return redirect('generator:realizar_simulado')

        # Redireciona para si mesmo (GET) para carregar a próxima questão ou finalizar
        return redirect('generator:realizar_simulado')

    # --- Lógica para GET (Exibe a questão atual ou finaliza) ---
    if not questao_ids:
        messages.warning(request, "Simulado não iniciado ou configuração perdida. Por favor, configure novamente.")
        logger.warning(f"GET realizar_simulado sem 'simulado_questao_ids' na sessão por {request.user.username}")
        return redirect('generator:configurar_simulado')

    # Verifica se o índice atual já ultrapassou a lista de questões (fim do simulado)
    if indice_atual >= len(questao_ids):
        messages.success(request, "Simulado concluído!")
        # Guarda os IDs finalizados para a página de resultado e limpa a sessão do simulado atual
        simulado_finalizado_ids = request.session.pop('simulado_questao_ids', [])
        request.session['finalizado_simulado_questao_ids'] = simulado_finalizado_ids # Guarda para resultado
        request.session.pop('simulado_indice_atual', None)
        # request.session.pop('simulado_respostas', None) # Removido se não usado
        # request.session.pop('simulado_config', None) # Pode manter config para exibir no resultado

        logger.info(f"Simulado finalizado para {request.user.username}. IDs: {simulado_finalizado_ids}. Redirecionando para resultados.")
        return redirect('generator:resultado_simulado') # Redireciona para a página de resultado

    # Se ainda há questões, busca a questão do índice atual para exibir
    questao_id_atual = questao_ids[indice_atual]
    try:
        questao_atual = Questao.objects.select_related('area').get(id=questao_id_atual)
        context['questao'] = questao_atual
        context['indice_atual'] = indice_atual + 1 # Para exibição (Questão 1 de N, 2 de N, ...)
        context['total_questoes'] = len(questao_ids)
        # Passa a configuração para o template, se existir
        context['simulado_config'] = request.session.get('simulado_config', {})

        logger.info(f"Exibindo questão índice {indice_atual} (ID: {questao_id_atual}) para {request.user.username}. Total: {len(questao_ids)}")
    except Questao.DoesNotExist:
        messages.error(request, f"Erro: A questão {indice_atual + 1} do simulado (ID: {questao_id_atual}) não foi encontrada.")
        logger.error(f"Questão ID {questao_id_atual} (índice {indice_atual}) não encontrada no DB durante GET realizar_simulado por {request.user.username}")
        request.session.pop('simulado_questao_ids', None); request.session.pop('simulado_indice_atual', None)
        return redirect('generator:configurar_simulado')
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar questão {questao_id_atual} para o simulado: {e}", exc_info=True)
        messages.error(request, "Ocorreu um erro ao carregar a próxima questão do simulado.")
        return redirect('generator:configurar_simulado') # Volta para configuração

    return render(request, 'generator/realizar_simulado.html', context)


# --- VIEW: Resultado do Simulado ---
@login_required
def resultado_simulado_view(request):
    """Exibe os resultados e estatísticas do último simulado concluído."""
    context, _, _ = _get_base_context_and_service()
    # Pega os IDs das questões do simulado finalizado da sessão
    # Usa .get() para não dar erro se a chave não existir, retorna lista vazia
    questao_ids = request.session.get('finalizado_simulado_questao_ids', [])
    simulado_config = request.session.get('simulado_config', {}) # Pega config também

    # Limpa as chaves da sessão após pegá-las (ou se não existirem)
    request.session.pop('finalizado_simulado_questao_ids', None)
    # request.session.pop('simulado_config', None) # Decide se quer limpar a config

    if not questao_ids:
        messages.warning(request, "Não há resultados de simulado para exibir ou a sessão expirou.")
        logger.warning(f"Acesso a resultado_simulado_view sem 'finalizado_simulado_questao_ids' por {request.user.username}")
        return redirect('generator:dashboard') # Ou para 'configurar_simulado'

    logger.info(f"Exibindo resultado do simulado para {request.user.username}. Questões IDs: {questao_ids}")

    tentativas_do_simulado = []
    stats_simulado = {}

    try:
        # Busca as tentativas e avaliações APENAS para as questões deste simulado
        # Garante que busca apenas as do usuário logado
        tentativas_do_simulado = TentativaResposta.objects.filter(
            usuario=request.user,
            questao_id__in=questao_ids # Filtra pelos IDs do simulado
        ).select_related(
            'questao', 'questao__area'
        ).prefetch_related(
            'avaliacao'
        ).order_by('data_resposta') # Ordena pela ordem de resposta (ou pode usar a ordem de questao_ids se preferir)

        # Calcula Estatísticas Específicas do Simulado
        total_respondidas = tentativas_do_simulado.count()
        total_ce = 0; acertos_ce = 0; erros_ce = 0
        # Adicione contadores para discursivas se simulados puderem incluí-las no futuro
        # total_disc = 0; ...

        for t in tentativas_do_simulado:
            if t.questao.tipo == 'CE':
                total_ce += 1
                avaliacao = getattr(t, 'avaliacao', None) # Pega do prefetch
                if avaliacao and avaliacao.correto_ce is not None:
                    if avaliacao.correto_ce: acertos_ce += 1
                    else: erros_ce += 1
            # elif t.questao.tipo == 'DISC':
                # Lógica para discursiva se aplicável no futuro

        # Stats C/E
        score_ce = acertos_ce - erros_ce
        # Calcula percentual baseado no total de C/E respondidas no simulado
        percentual_ce = round((acertos_ce / total_ce) * 100) if total_ce > 0 else 0

        stats_simulado = {
            'total_questoes_planejado': simulado_config.get('num_ce', len(questao_ids)), # Total planejado
            'total_respondidas': total_respondidas, # Total efetivamente respondido/salvo
            'total_ce': total_ce, # Total de C/E respondidas
            'acertos_ce': acertos_ce,
            'erros_ce': erros_ce,
            'score_ce': score_ce,
            'percentual_ce': percentual_ce,
            # Adicionar outras stats (discursivas) se necessário
            'config': simulado_config # Passa a configuração usada no simulado
        }
        logger.info(f"Stats do Simulado para {request.user.username}: {stats_simulado}")

        if total_respondidas < len(questao_ids):
             messages.warning(request, f"Atenção: Você respondeu {total_respondidas} de {len(questao_ids)} questões planejadas para este simulado.")

    except Exception as e:
        logger.error(f"Erro ao buscar/calcular resultado do simulado para {request.user.username} (IDs: {questao_ids}): {e}", exc_info=True)
        messages.error(request, "Ocorreu um erro ao carregar os resultados detalhados do simulado.")
        # Não limpa a lista de tentativas para debug se necessário
        stats_simulado = {'config': simulado_config} # Passa pelo menos a config

    context['tentativas_simulado'] = tentativas_do_simulado # Passa a lista de tentativas deste simulado
    context['stats_simulado'] = stats_simulado # Passa as estatísticas deste simulado

    return render(request, 'generator/resultado_simulado.html', context)
# --- FIM VIEW RESULTADO ---

@login_required # Apenas usuários logados podem ver/gerenciar
def area_list_view(request):
    """Lista todas as Áreas de Conhecimento cadastradas."""
    context, _, _ = _get_base_context_and_service()
    try:
        areas = AreaConhecimento.objects.all().order_by('nome') # Busca todas as áreas ordenadas
        context['areas'] = areas
    except Exception as e:
        logger.error(f"Erro ao listar Áreas de Conhecimento: {e}", exc_info=True)
        messages.error(request, "Erro ao carregar a lista de áreas.")
        context['areas'] = [] # Retorna lista vazia em caso de erro

    return render(request, 'generator/area_list.html', context)

@login_required
@require_POST # Garante que só aceite requisições POST
def add_area_quick_from_generator_view(request):
    """
    Processa a submissão do formulário de adição rápida de Área de Conhecimento
    a partir da página do gerador C/E e redireciona de volta.
    """
    # Instancia o formulário com os dados recebidos via POST
    form = AreaConhecimentoForm(request.POST)

    # Verifica se os dados do formulário são válidos
    if form.is_valid():
        try:
            # Cria o objeto AreaConhecimento sem salvar no banco ainda
            nova_area = form.save(commit=False)
            # Opcional: Associar o usuário que criou
            # nova_area.criado_por = request.user
            # Salva o objeto no banco de dados
            nova_area.save()
            # Obtém o nome da área salva para a mensagem
            nome_area = form.cleaned_data.get('nome')
            # Adiciona uma mensagem de sucesso para o usuário
            messages.success(request, f"Área '{nome_area}' adicionada com sucesso!")
            # Loga a ação
            logger.info(f"Área rápida adicionada (via Gerador C/E): '{nome_area}' por {request.user.username}")
        except Exception as e:
             # Em caso de erro ao salvar (ex: problema no DB)
             nome_area_tentativa = form.cleaned_data.get('nome', '[N/A]') # Pega nome se disponível
             logger.error(f"Erro ao salvar área rápida (via Gerador C/E) '{nome_area_tentativa}': {e}", exc_info=True)
             messages.error(request, f"Ocorreu um erro inesperado ao tentar salvar a área '{nome_area_tentativa}'.")
    else:
        # Se o formulário for inválido (ex: nome duplicado, vazio, etc.)
        # Constrói uma mensagem de erro a partir dos erros do formulário
        # Pega a primeira mensagem de erro de qualquer campo, se houver
        error_list = [f"{field}: {error[0]}" for field, error in form.errors.items()]
        erro_msg = "Erro ao adicionar área: " + (error_list[0] if error_list else "Verifique os dados.")
        # Loga os erros detalhados
        logger.warning(f"Tentativa inválida de adicionar Área Rápida (via Gerador C/E) por {request.user.username}: {form.errors.as_json()}")
        # Adiciona a mensagem de erro para o usuário
        messages.error(request, erro_msg)

    # Redireciona de volta para a página do gerador C/E,
    # independentemente de ter tido sucesso ou falha na adição da área.
    # As mensagens (success ou error) serão exibidas na página recarregada.
    return redirect('generator:generate_questions')

@login_required
def listar_questoes_ce_view(request):
    """
    Lista questões C/E com paginação e filtros: q (keyword), area (id).
    Também trata filtro por 'ids' vindo do redirect da geração.
    Passa todas as áreas para o contexto para o formulário de busca.
    """
    context = {}
    logger = logging.getLogger('generator')
    questoes_list = None
    is_filtered_list = False
    main_motivador = None
    id_list_str = request.GET.get('ids')
    query_filter_param = request.GET.get('q', '').strip()
    area_filter_param = request.GET.get('area', '')

    # Prioridade 1: Filtro por IDs específicos
    if id_list_str:
        # ... (lógica para filtrar por IDs e buscar main_motivador como antes) ...
        logger.info(f"Listando por IDs: [{id_list_str}]")
        try:
            id_list = [int(id_val.strip()) for id_val in id_list_str.split(',') if id_val.strip().isdigit()]
            if id_list:
                questoes_list = Questao.objects.filter(id__in=id_list).select_related('area', 'criado_por').order_by('id')
                is_filtered_list = True
                context['id_filter_param'] = id_list_str
                try:
                    first_q = questoes_list.first()
                    if first_q: main_motivador = first_q.texto_motivador
                except Exception as e_motiv: logger.error(f"Erro buscar motivador: {e_motiv}")
            else: messages.warning(request, "IDs inválidos.")
        except (ValueError, TypeError) as e: logger.error(f"Erro converter IDs: {e}"); messages.error(request, "Erro IDs.")

    # Prioridade 2: Filtro por 'q' ou 'area' (ou lista geral)
    if questoes_list is None:
        logger.info(f"Listando com filtros: q='{query_filter_param}', area='{area_filter_param}'")
        questoes_list = Questao.objects.filter(tipo='CE').select_related('area', 'criado_por')
        if query_filter_param:
            questoes_list = questoes_list.filter( Q(texto_comando__icontains=query_filter_param) | Q(texto_motivador__icontains=query_filter_param) | Q(id__icontains=query_filter_param) )
            is_filtered_list = True
        if area_filter_param and area_filter_param.isdigit():
            try:
                questoes_list = questoes_list.filter(area_id=int(area_filter_param))
                is_filtered_list = True
            except ValueError: messages.warning(request, f"ID Área inválido: {area_filter_param}"); area_filter_param = ''
        elif area_filter_param: messages.warning(request, f"Filtro Área inválido: {area_filter_param}"); area_filter_param = ''
        questoes_list = questoes_list.order_by('-criado_em')
        main_motivador = None

    # --- PAGINAÇÃO ---
    items_per_page = 20
    paginator = Paginator(questoes_list, items_per_page)
    page_number = request.GET.get('page')
    try: page_obj = paginator.get_page(page_number)
    except PageNotAnInteger: page_obj = paginator.get_page(1)
    except EmptyPage: page_obj = paginator.get_page(paginator.num_pages)

    # --- ADICIONA TUDO AO CONTEXTO ---
    context['page_obj'] = page_obj
    context['paginator'] = paginator
    context['is_filtered_list'] = is_filtered_list
    context['main_motivador'] = main_motivador
    context['id_filter_param'] = id_list_str
    context['query_filter_param'] = query_filter_param
    context['area_filter_param'] = area_filter_param

    # +++++ ADICIONA TODAS AS ÁREAS PARA O DROPDOWN DO FILTRO +++++
    try:
        context['all_areas'] = AreaConhecimento.objects.all().order_by('nome')
    except Exception as e_area:
        logger.error(f"Erro ao buscar todas as áreas para filtro: {e_area}")
        context['all_areas'] = None # Evita erro no template se a busca falhar
    # +++++ FIM ADIÇÃO all_areas +++++

    logger.info(f"Renderizando lista C/E. Filtrada: {is_filtered_list}. Página: {page_obj.number}/{paginator.num_pages}")

    # Renderiza o template de LISTAGEM
    return render(request, 'generator/questions_ce.html', context)

@login_required
def listar_questoes_discursivas_view(request):
    """
    Lista e filtra APENAS questões Discursivas com paginação.
    Filtros: q (keyword), area (id).
    """
    context = {}
    is_filtered_list = False
    query_filter_param = request.GET.get('q', '').strip()
    area_filter_param = request.GET.get('area', '')

    logger.info(f"Listando questões DISCURSIVAS com filtros: q='{query_filter_param}', area='{area_filter_param}'")
    questoes_list = Questao.objects.filter(tipo='DISC').select_related('area', 'criado_por')

    if query_filter_param:
        questoes_list = questoes_list.filter( Q(texto_comando__icontains=query_filter_param) | Q(id__icontains=query_filter_param) )
        is_filtered_list = True
    if area_filter_param and area_filter_param.isdigit():
        try:
            questoes_list = questoes_list.filter(area_id=int(area_filter_param))
            is_filtered_list = True
        except ValueError: messages.warning(request, f"ID Área inválido: {area_filter_param}"); area_filter_param = ''
    elif area_filter_param: messages.warning(request, f"Filtro Área inválido: {area_filter_param}"); area_filter_param = ''

    questoes_list = questoes_list.order_by('-criado_em')
    items_per_page = 20
    paginator = Paginator(questoes_list, items_per_page)
    page_number = request.GET.get('page')
    try: page_obj = paginator.get_page(page_number)
    except PageNotAnInteger: page_obj = paginator.get_page(1)
    except EmptyPage: page_obj = paginator.get_page(paginator.num_pages)

    context['page_obj'] = page_obj; context['paginator'] = paginator
    context['is_filtered_list'] = is_filtered_list
    context['query_filter_param'] = query_filter_param; context['area_filter_param'] = area_filter_param
    try: context['all_areas'] = AreaConhecimento.objects.all().order_by('nome')
    except Exception as e_area: logger.error(f"Erro buscar áreas: {e_area}"); context['all_areas'] = None

    logger.info(f"Renderizando lista DISCURSIVAS. Filtrada: {is_filtered_list}. Página: {page_obj.number}/{paginator.num_pages}")
    return render(request, 'generator/questions_discursivas.html', context)
# --- FIM DA VIEW listar_questoes_discursivas_view ---



