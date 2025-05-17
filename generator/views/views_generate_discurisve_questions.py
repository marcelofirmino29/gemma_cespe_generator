from django.contrib import messages
from venv import logger
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from generator.exceptions import AIResponseError, AIServiceError, ConfigurationError, GeneratorError, ParsingError
from generator.forms import DiscursiveExamForm
from generator.models import AreaConhecimento, Avaliacao, Questao, TentativaResposta
from django.utils import timezone
from venv import logger

from generator.models import Avaliacao, Questao, TentativaResposta
from generator.utils import parse_evaluation_scores
from generator.views.views_pdf_functions import extrair_texto_completo_pdf
from generator.views.views_service_context import _get_base_context_and_service
# # --- Sua função _get_base_context_and_service ---

@login_required
def generate_discursive_exam_view(request):
    base_context, service, service_initialized = _get_base_context_and_service()
    context = base_context.copy()
    context['service_initialized'] = service_initialized
    
    discursive_exam_text = None
    questao_id = None # Esta variável será usada para o ID da questão exibida (carregada ou gerada)

    if request.method == 'POST':
        # Esta seção é para GERAR UMA NOVA QUESTÃO
        form = DiscursiveExamForm(request.POST, request.FILES or None) # Adicionar request.FILES
        if form.is_valid():
            if not service_initialized or not service:
                messages.error(request, context.get('error_message', "Serviço de IA indisponível para processar."))
                context['form'] = form 
                return render(request, 'generator/discursive_exam_generator.html', context)

            base_topic_or_context_manual = form.cleaned_data.get('base_topic_or_context')
            pdf_file_uploaded = form.cleaned_data.get('pdf_file') # NOVO: Obter PDF
            
            final_context_for_ia = base_topic_or_context_manual # Começa com o texto manual

            if pdf_file_uploaded:
                try:
                    logger.info(f"Processando PDF '{pdf_file_uploaded.name}' para NOVA questão discursiva.")
                    texto_do_pdf = extrair_texto_completo_pdf(pdf_file_uploaded) # Certifique-se que extrair_texto_completo_pdf está importado
                    if texto_do_pdf and texto_do_pdf.strip():
                        final_context_for_ia = texto_do_pdf # PDF tem prioridade
                        if base_topic_or_context_manual and base_topic_or_context_manual.strip():
                            final_context_for_ia += "\n\n--- Tópico adicional fornecido manualmente ---\n" + base_topic_or_context_manual
                            messages.info(request, "Conteúdo do PDF combinado com texto manual para nova questão.")
                        # else:
                            # messages.info(request, "Conteúdo do PDF usado como base para nova questão.")
                        logger.info(f"Texto extraído do PDF para nova questão: {len(final_context_for_ia)} caracteres.")
                    elif not (base_topic_or_context_manual and base_topic_or_context_manual.strip()):
                        # PDF sem texto E texto manual vazio
                        messages.error(request, f"PDF '{pdf_file_uploaded.name}' não contém texto extraível e nenhum tópico manual foi fornecido.")
                        context['form'] = form
                        context['error_message'] = "Fonte de contexto insuficiente."
                        return render(request, 'generator/discursive_exam_generator.html', context)
                    # Se PDF sem texto, mas há texto manual, final_context_for_ia já é o texto manual
                except ValueError as e_pdf:
                    logger.error(f"Erro ao processar PDF para nova questão: {e_pdf}", exc_info=True)
                    messages.error(request, f"Erro ao processar o arquivo PDF: {e_pdf}")
                    if not (base_topic_or_context_manual and base_topic_or_context_manual.strip()):
                        context['form'] = form
                        context['error_message'] = "Erro no PDF e nenhum tópico manual fornecido."
                        return render(request, 'generator/discursive_exam_generator.html', context)
            
            # Verifica se temos um contexto final após processar PDF e/ou texto manual
            if not final_context_for_ia or not final_context_for_ia.strip():
                messages.error(request, "É necessário fornecer um tópico/contexto textual ou um PDF com conteúdo para gerar a questão.")
                context['form'] = form
                return render(request, 'generator/discursive_exam_generator.html', context)

            num_aspects = form.cleaned_data.get('num_aspects', 3)
            area_obj = form.cleaned_data.get('area')
            difficulty = form.cleaned_data.get('complexity', 'Intermediária') # No seu form original, parece que 'complexity' era o campo.
                                                                            # Se for 'difficulty_level' no DiscursiveExamForm, ajuste aqui.
            complexity_for_service = difficulty 
            language = form.cleaned_data.get('language', 'pt-br') # Pegar do form
            current_user = request.user if request.user.is_authenticated else None
            
            logger.info(f"POST Gerador Discursiva: Contexto_len={len(final_context_for_ia)}, Aspectos={num_aspects}, Área={area_obj}, Dificuldade={complexity_for_service}")

            try:
                # Esta chamada agora usa final_context_for_ia
                generated_text = service.generate_discursive_exam_question(
                    base_topic_or_context=final_context_for_ia, 
                    num_aspects=num_aspects, 
                    area=area_obj.nome if area_obj else None, 
                    complexity=complexity_for_service, 
                    language=language
                )
                
                if generated_text and isinstance(generated_text, str) and generated_text.strip():
                    # Mapear 'complexity_for_service' (ex: 'Intermediária') para os valores do modelo ('facil', 'medio', 'dificil')
                    dificuldade_db = 'medio' # Valor padrão
                    if complexity_for_service:
                        comp_lower = complexity_for_service.lower()
                        if comp_lower in ['fácil', 'facil', 'simples']: dificuldade_db = 'facil'
                        elif comp_lower in ['difícil', 'dificil', 'complexa']: dificuldade_db = 'dificil'

                    q = Questao(
                        tipo='DISC',
                        texto_comando=generated_text,
                        aspectos_discursiva=f"Avaliar {num_aspects} aspecto(s) solicitado(s).",
                        dificuldade=dificuldade_db, # Salva o valor mapeado
                        area=area_obj, 
                        criado_por=current_user
                    )
                    q.save()
                    questao_id = q.id # ID da questão GERADA
                    discursive_exam_text = generated_text # Texto da questão GERADA
                    logger.info(f"Questão Discursiva ID {questao_id} salva com sucesso.")
                    messages.success(request, f"Questão discursiva (ID: {questao_id}) gerada com sucesso! Você pode respondê-la abaixo ou buscar por ela mais tarde.")
                    # Não faz redirect aqui, exibe a questão gerada na mesma página.
                    # O form será re-renderizado (com ou sem dados, dependendo se você limpar)
                    form = DiscursiveExamForm() # Limpa o formulário após sucesso na geração

                else:
                    messages.warning(request, "A IA não retornou um texto válido para a questão discursiva.")
                    # discursive_exam_text e questao_id permanecem None
            except Exception as e: 
                logger.error(f"Erro ao gerar ou salvar questão discursiva: {e}", exc_info=True)
                messages.error(request, f"Falha durante a geração/salvamento da questão: {e}")
                # discursive_exam_text e questao_id permanecem None
        else: 
            logger.warning(f"Formulário Gerador Discursiva INVÁLIDO: {form.errors.as_json()}")
            messages.error(request, "Por favor, corrija os erros indicados no formulário.")
        
        context['form'] = form

    # --- Lógica GET ---
    else: # request.method == 'GET'
        form = DiscursiveExamForm() # Form vazio para nova geração
        
        questao_id_from_url = request.GET.get('questao_id')
        logger.debug(f"GET generate_discursive_exam por {request.user.username}. questao_id_from_url: {questao_id_from_url}")

        if questao_id_from_url and questao_id_from_url.isdigit():
            qid = int(questao_id_from_url)
            logger.info(f"Tentando carregar Questão Discursiva ID={qid} via GET.")
            try:
                # Certifique-se que get_object_or_404 está importado: from django.shortcuts import get_object_or_404
                questao_para_exibir = get_object_or_404(Questao, id=qid, tipo='DISC')
                discursive_exam_text = questao_para_exibir.texto_comando # Texto da questão CARREGADA
                questao_id = questao_para_exibir.id # ID da questão CARREGADA
                logger.info(f"Questão Discursiva ID {questao_id} carregada para exibição e resolução.")
                messages.info(request, f"Modo Resolução: Questão ID {questao_id} carregada. Responda abaixo.")
            except Questao.DoesNotExist:
                 logger.warning(f"Questão discursiva ID {qid} não encontrada.", exc_info=False) # exc_info=False para não poluir log por algo comum
                 messages.warning(request, f"A questão discursiva com ID {qid} não foi encontrada.")
                 # discursive_exam_text e questao_id permanecem None
            except Exception as e: 
                 logger.error(f"Erro ao buscar questão discursiva ID {qid} via GET: {e}", exc_info=True)
                 messages.error(request, f"Erro ao tentar carregar a questão discursiva com ID {qid}.")
                 # discursive_exam_text e questao_id permanecem None
        
        context['form'] = form

    context['discursive_exam_text'] = discursive_exam_text
    context['questao_id'] = questao_id # Esta é a chave para o template exibir a questão e a área de resposta

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
