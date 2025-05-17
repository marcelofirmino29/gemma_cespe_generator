import logging
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.urls import reverse
from django.db.models import Q
from generator.forms import QuestionGeneratorForm
from generator.models import AreaConhecimento, Questao

from generator.models import Questao
from generator.views.views_pdf_functions import extrair_texto_completo_pdf
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
def listar_questoes_ce_view(request):
    """
    Lista questões C/E com paginação e filtros: q (keyword), area (lista de IDs).
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
    
    # Modificado para lidar com múltiplos IDs de área
    area_filter_params_str = request.GET.getlist('area') # Recebe uma lista de strings (IDs das áreas)

    # Prioridade 1: Filtro por IDs específicos (vindo da geração de questões)
    if id_list_str:
        logger.info(f"Listando por IDs específicos: [{id_list_str}]")
        try:
            id_list = [int(id_val.strip()) for id_val in id_list_str.split(',') if id_val.strip().isdigit()]
            if id_list:
                # Certifique-se de que Questao.objects está disponível
                if Questao.objects:
                    questoes_list = Questao.objects.filter(id__in=id_list).select_related('area', 'criado_por').order_by('id')
                    is_filtered_list = True
                    context['id_filter_param'] = id_list_str # Mantém para saber que veio da geração
                    try:
                        first_q = questoes_list.first()
                        if first_q:
                            main_motivador = first_q.texto_motivador
                    except Exception as e_motiv:
                        logger.error(f"Erro ao buscar texto motivador para lista de IDs: {e_motiv}")
                else:
                    messages.error(request, "Modelo Questao não carregado corretamente.") # pragma: no cover
            else:
                messages.warning(request, "IDs fornecidos para filtro são inválidos.")
        except (ValueError, TypeError) as e:
            logger.error(f"Erro ao converter IDs da lista: {e}")
            messages.error(request, "Erro ao processar IDs para filtro.")

    # Prioridade 2: Filtro por palavra-chave 'q' e/ou lista de 'area_ids' (ou lista geral se nenhum filtro)
    if questoes_list is None: # Só executa se o filtro por IDs específicos não foi aplicado ou falhou
        log_msg_parts = []
        if query_filter_param:
            log_msg_parts.append(f"q='{query_filter_param}'")
        if area_filter_params_str:
            log_msg_parts.append(f"areas='{','.join(area_filter_params_str)}'")
        
        logger.info(f"Listando questões C/E com filtros: {', '.join(log_msg_parts) if log_msg_parts else 'Geral (sem filtros específicos q/area)'}")

        if not Questao.objects: # pragma: no cover
            messages.error(request, "Modelo Questao não carregado corretamente.")
            # Retorna o render aqui ou define questoes_list como uma lista vazia para evitar erros na paginação
            context['page_obj'] = None
            context['paginator'] = None
            # Adicionar outras chaves do contexto como None ou valor padrão
            context['is_filtered_list'] = False
            context['main_motivador'] = None
            context['id_filter_param'] = None
            context['query_filter_param'] = query_filter_param
            context['area_filter_param'] = area_filter_params_str # Passa os params originais para o template
            context['all_areas'] = AreaConhecimento.objects.all().order_by('nome') if AreaConhecimento.objects else []
            return render(request, 'generator/questions_ce.html', context)

        base_queryset = Questao.objects.filter(tipo='CE').select_related('area', 'criado_por')

        if query_filter_param:
            base_queryset = base_queryset.filter(
                Q(texto_comando__icontains=query_filter_param) |
                Q(texto_motivador__icontains=query_filter_param) |
                Q(id__icontains=query_filter_param)  # Permitir busca por ID numérico também
            )
            is_filtered_list = True
        
        # Nova lógica para filtrar por múltiplas áreas
        valid_area_ids = []
        if area_filter_params_str: # Se a lista não estiver vazia
            has_valid_area_filter = False
            for area_id_str in area_filter_params_str:
                if area_id_str.strip().isdigit(): # Verifica se é um ID numérico válido
                    valid_area_ids.append(int(area_id_str.strip()))
                    has_valid_area_filter = True
                elif area_id_str.strip(): # Se não for numérico mas não for vazio (ex: "-- Todas --" que tem value="")
                    messages.warning(request, f"Filtro de área inválido ou não numérico ignorado: '{area_id_str}'.")
            
            if valid_area_ids:
                base_queryset = base_queryset.filter(area_id__in=valid_area_ids)
                is_filtered_list = True # Marcado como filtrado se ao menos um ID de área válido foi usado
            elif area_filter_params_str and not any(s.strip() for s in area_filter_params_str):
                # Caso onde 'area' foi enviado mas era uma lista de strings vazias (improvável com select multiple padrão)
                # ou apenas a opção "Todas as áreas" foi selecionada e enviou um value=""
                pass # Não filtra por área se apenas value="" foi enviado
            elif area_filter_params_str and not has_valid_area_filter : # Se havia params de área mas nenhum era ID válido
                 messages.warning(request, "Nenhum ID de área válido foi fornecido para o filtro. Exibindo todas as áreas que correspondem a outros filtros.")


        questoes_list = base_queryset.order_by('-criado_em')
        main_motivador = None # Para busca geral/filtrada, o motivador principal não é aplicável como na geração.

    # --- PAGINAÇÃO ---
    # Garante que questoes_list seja uma lista ou queryset antes de paginar
    if questoes_list is None:
        questoes_list = [] # Evita erro se nenhuma query anterior populou questoes_list

    items_per_page = getattr(settings, 'ITEMS_PER_PAGE_QUESTOES_CE', 20) # Usar uma config específica se houver
    paginator = Paginator(questoes_list, items_per_page)
    page_number = request.GET.get('page')

    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)

    # --- ADICIONA TUDO AO CONTEXTO ---
    context['page_obj'] = page_obj
    context['paginator'] = paginator
    context['is_filtered_list'] = is_filtered_list
    context['main_motivador'] = main_motivador
    context['id_filter_param'] = id_list_str # Se veio da geração, será preenchido
    context['query_filter_param'] = query_filter_param
    
    # Importante: area_filter_param no contexto deve ser a lista de strings dos IDs das áreas selecionadas
    # para que o template possa marcar corretamente as options no select multiple.
    context['area_filter_param'] = area_filter_params_str

    # +++++ ADICIONA TODAS AS ÁREAS PARA O DROPDOWN DO FILTRO +++++
    try:
        if AreaConhecimento.objects:
            context['all_areas'] = AreaConhecimento.objects.all().order_by('nome')
        else: # pragma: no cover
            context['all_areas'] = []
            messages.error(request, "Modelo AreaConhecimento não carregado.")
    except Exception as e_area: # pragma: no cover
        logger.error(f"Erro ao buscar todas as áreas para filtro: {e_area}")
        context['all_areas'] = [] # Evita erro no template se a busca falhar
        messages.error(request, "Erro ao carregar lista de áreas para filtro.")
    # +++++ FIM ADIÇÃO all_areas +++++

    logger.info(f"Renderizando lista C/E. Filtrada: {is_filtered_list}. Página: {page_obj.number if page_obj else 'N/A'} de {paginator.num_pages if paginator else 'N/A'}")

    # Renderiza o template de LISTAGEM
    return render(request, 'generator/questions_ce.html', context)
