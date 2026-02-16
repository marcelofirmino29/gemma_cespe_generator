import logging
logger = logging.getLogger(__name__)  # ✅ CORRIGIDO
import PyPDF2
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
from django.contrib import messages
from django.shortcuts import render
from generator.exceptions import AIServiceError, ConfigurationError, ParsingError
from generator.forms import PDFSummaryForm, PDFUploadForm
from generator.models import AreaConhecimento, Questao, TentativaResposta
from generator.services import QuestionGenerationService
from generator.views.views_service_context import _get_base_context_and_service

def extrair_texto_completo_pdf(uploaded_file_obj):
    """Extrai todo o texto de um objeto de arquivo PDF enviado usando PyPDF2."""
    texto_completo = []
    try:
        uploaded_file_obj.seek(0)
        reader = PyPDF2.PdfReader(uploaded_file_obj)
        num_paginas = len(reader.pages)
        
        if num_paginas == 0:
            logger.warning(f"PyPDF2: PDF '{uploaded_file_obj.name}' não contém páginas.")
            return ""

        logger.info(f"Lendo PDF '{uploaded_file_obj.name}' com {num_paginas} página(s) usando PyPDF2.")
        
        for i in range(num_paginas):
            page = reader.pages[i]
            texto_pagina = page.extract_text()
            if texto_pagina:
                texto_completo.append(texto_pagina)
        
        texto_final = "\n".join(texto_completo)
        
        if not texto_final.strip():
            logger.warning(f"PyPDF2 não conseguiu extrair texto legível do PDF: '{uploaded_file_obj.name}'.")
            return ""
            
        logger.info(f"PyPDF2 extraiu {len(texto_final)} caracteres de '{uploaded_file_obj.name}'.")
        return texto_final
    except PyPDF2.errors.PdfReadError as e_read:
        logger.error(f"PyPDF2: Erro de leitura do PDF '{uploaded_file_obj.name}': {e_read}", exc_info=True)
        raise ValueError(f"O arquivo PDF '{uploaded_file_obj.name}' parece estar corrompido ou não é um PDF válido.")
    except Exception as e:
        logger.error(f"PyPDF2: Erro inesperado ao extrair texto do PDF '{uploaded_file_obj.name}': {e}", exc_info=True)
        raise ValueError(f"Erro ao processar o conteúdo do PDF com PyPDF2: {e}")

@login_required
def dashboard_view(request):
    context, _, _ = _get_base_context_and_service()
    tentativas_recentes = []
    stats = {}
    date_from_obj = None
    date_to_obj = None

    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    area_filter_id = request.GET.get('area_filter')

    if date_from_str:
        try:
            date_from_obj = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError:
            messages.warning(request, "Formato de data inicial inválido. Use AAAA-MM-DD.")
            date_from_obj = None

    if date_to_str:
        try:
            date_to_obj = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            messages.warning(request, "Formato de data final inválido. Use AAAA-MM-DD.")
            date_to_obj = None

    area_filter_obj = None
    if area_filter_id:
        try:
            area_filter_obj = AreaConhecimento.objects.get(id=area_filter_id)
        except (AreaConhecimento.DoesNotExist, ValueError):
            messages.warning(request, "Área selecionada inválida.")
            area_filter_obj = None

    logger.info(f"Dashboard acessado por {request.user.username}. Filtros: Data=({date_from_str} a {date_to_str}), AreaID={area_filter_id}")

    try:
        todas_tentativas_qs = (
            TentativaResposta.objects
            .filter(usuario=request.user)
            .select_related('questao')
            .prefetch_related('avaliacao')
        )

        if date_from_obj:
            todas_tentativas_qs = todas_tentativas_qs.filter(data_resposta__date__gte=date_from_obj)

        if date_to_obj:
            date_to_inclusive = date_to_obj + timedelta(days=1)
            todas_tentativas_qs = todas_tentativas_qs.filter(data_resposta__lt=date_to_inclusive)

        if area_filter_obj:
            todas_tentativas_qs = todas_tentativas_qs.filter(questao__area=area_filter_obj)

        total_geral_filtrado = todas_tentativas_qs.count()

        # ✅ CORRIGIDO: C/E SEM CELERY
        ce_qs = todas_tentativas_qs.filter(questao__tipo='CE')
        total_ce_filtrado = ce_qs.count()
        acertos_ce = 0
        erros_ce = 0
        for t_ce in ce_qs:
            avaliacao = getattr(t_ce, 'avaliacao', None)
            if avaliacao and avaliacao.correto_ce is not None:
                if avaliacao.correto_ce:
                    acertos_ce += 1
                else:
                    erros_ce += 1
        score_ce = acertos_ce - erros_ce
        percentual_ce = round((acertos_ce / total_ce_filtrado) * 100) if total_ce_filtrado > 0 else 0

        # Discursivas
        tentativas_disc_filtradas = todas_tentativas_qs.filter(questao__tipo='DISC')
        total_disc_filtrado = tentativas_disc_filtradas.count()
        nc_total = 0.0
        ne_total = 0
        npd_total = 0.0
        count_disc_avaliadas = 0

        for t_disc in tentativas_disc_filtradas:
            avaliacao = getattr(t_disc, 'avaliacao', None)
            if (avaliacao and avaliacao.nc is not None and avaliacao.ne is not None and avaliacao.npd is not None):
                nc_total += avaliacao.nc
                ne_total += avaliacao.ne
                npd_total += avaliacao.npd
                count_disc_avaliadas += 1

        media_nc = round(nc_total / count_disc_avaliadas, 2) if count_disc_avaliadas > 0 else None
        media_ne = round(ne_total / count_disc_avaliadas, 2) if count_disc_avaliadas > 0 else None
        media_npd = round(npd_total / count_disc_avaliadas, 2) if count_disc_avaliadas > 0 else None

        stats = {
            'total_geral': total_geral_filtrado,
            'total_ce': total_ce_filtrado,
            'acertos_ce': acertos_ce,
            'erros_ce': erros_ce,
            'score_ce': score_ce,
            'percentual_ce': percentual_ce,
            'total_disc': total_disc_filtrado,
            'total_disc_avaliadas': count_disc_avaliadas,
            'media_nc': media_nc,
            'media_ne': media_ne,
            'media_npd': media_npd,
        }

        logger.info(f"Stats Dashboard (Filtrado) {request.user.username}: {stats}")
        tentativas_recentes = todas_tentativas_qs.order_by('-data_resposta')[:20]

    except Exception as e:
        logger.error(f"Erro ao carregar dados do dashboard para {request.user.username}: {e}", exc_info=True)
        messages.error(request, "Ocorreu um erro ao carregar seu desempenho. Tente novamente mais tarde.")
        tentativas_recentes = []
        stats = {}

    context['tentativas_list'] = tentativas_recentes
    context['stats'] = stats
    context['current_date_from'] = date_from_obj
    context['current_date_to'] = date_to_obj
    context['current_area_filter'] = area_filter_obj
    context['all_areas'] = AreaConhecimento.objects.all().order_by('nome')

    return render(request, 'generator/dashboard.html', context)

@login_required
def upload_pdf_and_generate_questions_view(request):
    form = PDFUploadForm()
    generated_questions_ce_data_with_ids = []
    generated_discursive_question_text = None
    motivador_texto_ce = None
    attempted_ce_generation = False
    attempted_discursive_generation = False

    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = form.cleaned_data['pdf_file']
            num_questions_ce = form.cleaned_data.get('num_questions_ce', 0)
            num_aspects_discursive = form.cleaned_data.get('num_aspects_discursive', 0)
            difficulty = form.cleaned_data['difficulty_level']
            area_obj = form.cleaned_data.get('area')
            current_user = request.user if request.user.is_authenticated else None

            # ✅ USA FUNÇÃO CENTRALIZADA
            extracted_text = extrair_texto_completo_pdf(pdf_file)
            
            if not extracted_text.strip():
                messages.error(request, "Não foi possível extrair texto do PDF. Verifique o arquivo.")
            else:
                logger.info(f"Texto extraído do PDF ({pdf_file.name}): {len(extracted_text)} caracteres.")

                try:
                    service = QuestionGenerationService()
                    
                    if num_questions_ce > 0:
                        attempted_ce_generation = True
                        logger.info(f"Tentando gerar {num_questions_ce} questões C/E para PDF: {pdf_file.name}")
                        
                        motivador_ce_str, questoes_ce_list_from_service = service.generate_questions(
                            topic=extracted_text, 
                            num_questions=num_questions_ce,
                            difficulty_level=difficulty,
                            area=area_obj 
                        )
                        
                        if questoes_ce_list_from_service:
                            saved_ce_count = 0
                            temp_generated_data_with_ids = []

                            for q_data_from_service in questoes_ce_list_from_service:
                                try:
                                    questao_salva = Questao.objects.create(
                                        tipo='CE', 
                                        texto_comando=q_data_from_service.get('afirmacao', 'Afirmação não fornecida'),
                                        texto_motivador=(motivador_ce_str if motivador_ce_str and motivador_ce_str.strip().lower() != "não aplicável" else None),
                                        gabarito_ce=q_data_from_service.get('gabarito', 'C'), 
                                        justificativa_gabarito=q_data_from_service.get('justificativa', ''), 
                                        dificuldade=difficulty,
                                        area=area_obj, 
                                        criado_por=current_user
                                    )
                                    saved_ce_count += 1
                                    temp_generated_data_with_ids.append({
                                        'id': questao_salva.id,
                                        'afirmacao': q_data_from_service.get('afirmacao'),
                                        'gabarito': q_data_from_service.get('gabarito'),
                                        'justificativa': q_data_from_service.get('justificativa')
                                    })
                                except Exception as e_save_ce:
                                    logger.error(f"Erro ao salvar Questao C/E: {e_save_ce} - Dados: {q_data_from_service}")
                                    messages.error(request, f"Erro ao salvar uma questão C/E: '{q_data_from_service.get('afirmacao', 'ID Desconhecido')[:50]}...'. Detalhes no log.")
                            
                            if saved_ce_count > 0:
                                logger.info(f"{saved_ce_count} Questões C/E salvas.")
                                messages.success(request, f"{saved_ce_count} de {len(questoes_ce_list_from_service)} questões C/E geradas e salvas com sucesso!")
                            
                            motivador_texto_ce = motivador_ce_str 
                            generated_questions_ce_data_with_ids = temp_generated_data_with_ids

                        elif motivador_ce_str and motivador_ce_str.strip().lower() != "não aplicável": 
                            messages.info(request, "Texto motivador para C/E foi preparado, mas nenhuma questão C/E específica foi gerada/retornada pelo serviço.")
                            motivador_texto_ce = motivador_ce_str 
                        else: 
                            messages.warning(request, "A tentativa de gerar questões C/E não produziu resultados (nem motivador, nem itens).")

                    if num_aspects_discursive > 0:
                        attempted_discursive_generation = True
                        logger.info(f"Tentando gerar questão discursiva com {num_aspects_discursive} aspectos para PDF: {pdf_file.name}")
                        
                        questao_discursiva_texto_completo_str = service.generate_discursive_exam_question(
                            base_topic_or_context=extracted_text, 
                            num_aspects=num_aspects_discursive,
                            complexity=difficulty,
                            area=area_obj 
                        )
                        
                        if questao_discursiva_texto_completo_str:
                            try:
                                questao_disc_salva = Questao.objects.create(
                                    tipo='DISC',
                                    texto_comando=questao_discursiva_texto_completo_str,
                                    aspectos_discursiva=f"Questão gerada a partir de PDF com {num_aspects_discursive} aspecto(s) solicitado(s).",
                                    dificuldade=difficulty,
                                    area=area_obj, 
                                    criado_por=current_user
                                )
                                logger.info(f"Questao Discursiva ID {questao_disc_salva.id} salva com sucesso.")
                                messages.success(request, "Questão discursiva gerada e salva com sucesso!")
                                generated_discursive_question_text = questao_discursiva_texto_completo_str 
                            except Exception as e_save_disc:
                                logger.error(f"Erro ao salvar Questao Discursiva: {e_save_disc}")
                                messages.error(request, "Erro ao salvar a questão discursiva no banco.")
                                generated_discursive_question_text = questao_discursiva_texto_completo_str 
                        else:
                            messages.warning(request, "A tentativa de gerar questão discursiva não produziu resultados.")
                    
                    if not attempted_ce_generation and not attempted_discursive_generation:
                        messages.info(request, "Nenhuma quantidade de questões C/E ou aspectos para questão discursiva foi especificada para geração.")
                        
                except ConfigurationError as e:
                    logger.error(f"Erro de configuração do serviço de IA: {e}")
                    messages.error(request, f"Erro de configuração do sistema: {e}")
                except AIServiceError as e:
                    logger.error(f"Erro no serviço de IA ao gerar questões do PDF: {e}")
                    messages.error(request, f"Erro ao comunicar com o serviço de IA: {e}")
                except ParsingError as e:
                    logger.error(f"Erro de parsing da resposta da IA para questões do PDF: {e}")
                    messages.error(request, f"Erro ao processar a resposta da IA: {e}")
                except Exception as e: 
                    logger.error(f"Erro inesperado ao gerar questões do PDF: {e}", exc_info=True)
                    messages.error(request, f"Ocorreu um erro inesperado durante a geração das questões: {e}")
                    generated_questions_ce_data_with_ids = []
                    motivador_texto_ce = None
                    generated_discursive_question_text = None
        else: 
            messages.error(request, "Houve um erro no formulário. Por favor, verifique os dados inseridos.")
    
    context = {
        'form': form,
        'generated_questions_ce_data': generated_questions_ce_data_with_ids,
        'motivador_texto_ce': motivador_texto_ce,
        'generated_discursive_question_text': generated_discursive_question_text,
    }
    return render(request, 'generator/upload_pdf_form.html', context)

@login_required
def pdf_summary_view(request):
    context, service, _ = _get_base_context_and_service()
    form = PDFSummaryForm()
    resumo_gerado = None

    if request.method == 'POST':
        form = PDFSummaryForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = form.cleaned_data['pdf_file']
            try:
                logger.info(f"Iniciando resumo para o arquivo: {pdf_file.name} por {request.user.username}")
                texto_extraido = extrair_texto_completo_pdf(pdf_file)

                if not texto_extraido.strip():
                    messages.error(request, "Não foi possível extrair texto do PDF. Verifique se o arquivo contém texto selecionável ou não está protegido/corrompido.")
                    return render(request, 'generator/pdf_summary.html', {'form': form, 'resumo_gerado': None, **context})

                MAX_CHARS_FOR_SUMMARY_PROMPT = 25000
                if len(texto_extraido) > MAX_CHARS_FOR_SUMMARY_PROMPT:
                    texto_para_resumo = texto_extraido[:MAX_CHARS_FOR_SUMMARY_PROMPT]
                    messages.warning(request, f"O texto do PDF é muito longo ({len(texto_extraido)} caracteres). Apenas os primeiros {MAX_CHARS_FOR_SUMMARY_PROMPT} caracteres serão usados para o resumo.")
                else:
                    texto_para_resumo = texto_extraido

                prompt_resumo = f"**Persona:** Você é um especialista em preparação para concursos públicos, com profundo conhecimento em identificar nuances e pontos críticos em textos jurídicos e técnicos.\n\n**Tarefa Principal:** Analisar o texto fornecido e produzir um resumo estratégico focado em concursos.\n\n**Texto Original para Análise:**\n```\n{texto_para_resumo}\n```\n\n**Instruções Detalhadas para o Resumo Estratégico:**\n\n1. **Sumarização Direta e Concisa:**\n   * Inicie com um resumo geral do tema central do texto (2-3 frases no máximo).\n   * Evite frases introdutórias genéricas como 'Este texto trata de...' ou 'O resumo a seguir...'. Vá direto ao ponto.\n\n2. **Identificação de Pontos Críticos para Concursos (Máximo de 5-7 pontos):**\n   * Analise o texto minuciosamente para identificar aspectos que são frequentemente objeto de questionamento em provas de concurso.\n   * **Exceções a regras gerais.**\n   * **Prazos e condições específicas.**\n   * **Competências e atribuições.**\n   * **Requisitos e vedações.**\n   * **Classificações e nomenclaturas importantes.**\n   * **Entendimentos jurisprudenciais ou doutrinários relevantes.**\n   * **Detalhes que podem gerar confusão ou 'pegadinhas' comuns.**\n\n**Formato Obrigatório de Saída:**\n\n**Resumo Geral do Tema:**\n[Aqui o resumo geral conciso do tema central do texto]\n\n**Pontos Críticos para Concursos:**\n1. **Ponto Crítico:** [Descrição]\n   **Relevância:** [Por que cai em prova]\n\n**Principais Tópicos:**\n* [Lista concisa]"

                logger.info(f"Enviando {len(texto_para_resumo)} caracteres para sumarização pela IA.")
                resumo_gerado = service.get_ai_response(prompt_resumo)
                messages.success(request, "Resumo gerado com sucesso!")
                logger.info(f"Resumo gerado para {pdf_file.name}.")

            except ValueError as e:
                logger.error(f"Erro ao extrair texto do PDF para resumo: {e}", exc_info=True)
                messages.error(request, str(e))
            except ConfigurationError as e:
                logger.error(f"Erro de configuração do serviço de IA para resumo: {e}", exc_info=True)
                messages.error(request, f"Erro de configuração do sistema ao tentar resumir: {e}")
            except AIServiceError as e:
                logger.error(f"Erro no serviço de IA ao tentar resumir: {e}", exc_info=True)
                messages.error(request, f"Erro ao comunicar com o serviço de IA para resumo: {e}")
            except Exception as e:
                logger.error(f"Erro inesperado ao gerar resumo do PDF: {e}", exc_info=True)
                messages.error(request, f"Ocorreu um erro inesperado durante a geração do resumo: {e}")
        else:
            messages.error(request, "Houve um erro no formulário. Por favor, verifique os dados inseridos.")

    context.update({'form': form, 'resumo_gerado': resumo_gerado})
    return render(request, 'generator/pdf_summary.html', context)
