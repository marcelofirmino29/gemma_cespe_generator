import logging
from venv import logger
import PyPDF2
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render
from generator.exceptions import AIServiceError, ConfigurationError, ParsingError
from generator.forms import PDFSummaryForm, PDFUploadForm
from generator.models import Questao
from generator.services import QuestionGenerationService
from generator.views.views_service_context import _get_base_context_and_service

def extrair_texto_completo_pdf(uploaded_file_obj):
    """
    Extrai todo o texto de um objeto de arquivo PDF enviado usando PyPDF2.
    Retorna o texto extraído ou uma string vazia se não houver texto.
    Levanta ValueError em caso de erro de processamento do PDF.
    """
    texto_completo = [] # Usar lista para juntar no final é mais eficiente
    try:
        # Garante que o ponteiro do arquivo esteja no início
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
        
        texto_final = "\n".join(texto_completo) # Junta as páginas com uma nova linha
        
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
# --- FIM DA FUNÇÃO DE EXTRAÇÃO DE TEXTO ---

# @login_required 
def upload_pdf_and_generate_questions_view(request):
    form = PDFUploadForm()
    # Esta lista agora conterá dicionários com os dados da IA E o ID da questão salva
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

            extracted_text = ""
            try:
                reader = PyPDF2.PdfReader(pdf_file)
                for page_num in range(len(reader.pages)):
                    page = reader.pages[page_num]
                    extracted_text += page.extract_text() or ""
                
                if not extracted_text.strip():
                    messages.error(request, "Não foi possível extrair texto do PDF. Verifique o arquivo.")
                    return render(request, 'generator/upload_pdf_form.html', {'form': form, 'generated_questions_ce_data_with_ids': [], 'motivador_texto_ce': None, 'generated_discursive_question_text': None})
                logger.info(f"Texto extraído do PDF ({pdf_file.name}): {len(extracted_text)} caracteres.")

            except Exception as e:
                logger.error(f"Erro ao extrair texto do PDF: {e}", exc_info=True)
                messages.error(request, f"Ocorreu um erro ao processar o arquivo PDF: {e}")
                return render(request, 'generator/upload_pdf_form.html', {'form': form, 'generated_questions_ce_data_with_ids': [], 'motivador_texto_ce': None, 'generated_discursive_question_text': None})

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
                        temp_generated_data_with_ids = [] # Lista temporária para os dados com ID

                        for q_data_from_service in questoes_ce_list_from_service:
                            try:
                                # ADAPTE OS NOMES DOS CAMPOS (LADO ESQUERDO) PARA CORRESPONDER AO SEU MODELO 'Questao'
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
                                # Adiciona os dados originais da IA E o ID da questão salva
                                temp_generated_data_with_ids.append({
                                    'id': questao_salva.id, # ID da questão salva
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
                        generated_questions_ce_data_with_ids = temp_generated_data_with_ids # Usa a lista com IDs

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
                            # ADAPTE OS NOMES DOS CAMPOS (LADO ESQUERDO) PARA CORRESPONDER AO SEU MODELO 'Questao'
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
                            # Para a discursiva, geralmente só exibimos o texto. Se precisar do ID no template, passe também.
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
        'generated_questions_ce_data': generated_questions_ce_data_with_ids, # Passa a lista com IDs
        'motivador_texto_ce': motivador_texto_ce,
        'generated_discursive_question_text': generated_discursive_question_text,
    }
    return render(request, 'generator/upload_pdf_form.html', context)

# --- NOVA VIEW: Resumo Rápido de PDF ---
@login_required
def pdf_summary_view(request):
    context, service, _ = _get_base_context_and_service() # Pega o contexto base e o serviço de IA
    form = PDFSummaryForm()
    resumo_gerado = None

    if request.method == 'POST':
        form = PDFSummaryForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = form.cleaned_data['pdf_file']
            texto_extraido = ""
            try:
                logging.info(f"Iniciando resumo para o arquivo: {pdf_file.name} por {request.user.username}")
                texto_extraido = extrair_texto_completo_pdf(pdf_file)

                if not texto_extraido.strip():
                    messages.error(request, "Não foi possível extrair texto do PDF. Verifique se o arquivo contém texto selecionável ou não está protegido/corrompido.")
                    # Não redireciona, apenas re-renderiza com a mensagem de erro
                    return render(request, 'generator/pdf_summary.html', {'form': form, 'resumo_gerado': None, **context})


                # Define um limite de caracteres para o prompt para evitar exceder limites da API
                # Este é um exemplo, ajuste conforme necessário e de acordo com os limites do modelo da IA.
                MAX_CHARS_FOR_SUMMARY_PROMPT = 25000 # Ajuste conforme necessário
                if len(texto_extraido) > MAX_CHARS_FOR_SUMMARY_PROMPT:
                    texto_para_resumo = texto_extraido[:MAX_CHARS_FOR_SUMMARY_PROMPT]
                    messages.warning(request, f"O texto do PDF é muito longo ({len(texto_extraido)} caracteres). Apenas os primeiros {MAX_CHARS_FOR_SUMMARY_PROMPT} caracteres serão usados para o resumo.")
                else:
                    texto_para_resumo = texto_extraido

# Dentro da sua view pdf_summary_view, após extrair 'texto_para_resumo':

                prompt_resumo = (
                    f"**Persona:** Você é um especialista em preparação para concursos públicos, com profundo conhecimento em identificar nuances e pontos críticos em textos jurídicos e técnicos.\n\n"
                    f"**Tarefa Principal:** Analisar o texto fornecido e produzir um resumo estratégico focado em concursos.\n\n"
                    f"**Texto Original para Análise:**\n"
                    f"```\n"
                    f"{texto_para_resumo}\n"
                    f"```\n\n"
                    f"**Instruções Detalhadas para o Resumo Estratégico:**\n\n"
                    f"1.  **Sumarização Direta e Concisa:**\n"
                    f"    * Inicie com um resumo geral do tema central do texto (2-3 frases no máximo).\n"
                    f"    * Evite frases introdutórias genéricas como 'Este texto trata de...' ou 'O resumo a seguir...'. Vá direto ao ponto.\n\n"
                    f"2.  **Identificação de Pontos Críticos para Concursos (Máximo de 5-7 pontos):**\n"
                    f"    * Analise o texto minuciosamente para identificar aspectos que são frequentemente objeto de questionamento em provas de concurso. Isso inclui, mas não se limita a:\n"
                    f"        * **Exceções a regras gerais.**\n"
                    f"        * **Prazos e condições específicas.**\n"
                    f"        * **Competências e atribuições.**\n"
                    f"        * **Requisitos e vedações.**\n"
                    f"        * **Classificações e nomenclaturas importantes.**\n"
                    f"        * **Entendimentos jurisprudenciais ou doutrinários relevantes (se mencionados ou implícitos).**\n"
                    f"        * **Detalhes que podem gerar confusão ou 'pegadinhas' comuns.**\n"
                    f"    * Para cada ponto crítico identificado, explique-o de forma clara e objetiva, destacando por que é relevante para concursos.\n\n"
                    f"3.  **Principais Conclusões/Tópicos Relevantes:**\n"
                    f"    * Liste os principais argumentos, tópicos ou conclusões do texto que um candidato precisa reter.\n\n"
                    f"**Formato Obrigatório de Saída (Use EXATAMENTE esta estrutura e os marcadores em negrito):**\n\n"
                    f"**Resumo Geral do Tema:**\n"
                    f"[Aqui o resumo geral conciso do tema central do texto]\n\n"
                    f"**Pontos Críticos para Concursos (Análise Detalhada):**\n\n"
                    f"1.  **Ponto Crítico:** [Descrição do primeiro ponto crítico/detalhe/exceção]\n"
                    f"    **Relevância/Alerta para Concurso:** [Explicação de por que este ponto é crucial ou pode ser uma pegadinha]\n\n"
                    f"2.  **Ponto Crítico:** [Descrição do segundo ponto crítico/detalhe/exceção]\n"
                    f"    **Relevância/Alerta para Concurso:** [Explicação]\n\n"
                    f"    *(Continue com até 5-7 pontos, se aplicável)*\n\n"
                    f"**Principais Tópicos e Conclusões do Texto:**\n"
                    f"* [Primeiro tópico/conclusão principal]\n"
                    f"* [Segundo tópico/conclusão principal]\n"
                    f"* [E assim por diante...]\n"
                )

                # logging.info(f"Enviando {len(texto_para_resumo)} caracteres para sumarização pela IA com prompt AVANÇADO.")
                # resumo_gerado = service.get_ai_response(prompt_resumo_avancado)
                # messages.success(request, "Resumo estratégico gerado com sucesso!")
                # logging.info(f"Resumo estratégico gerado para {pdf_file.name}.")


                logging.info(f"Enviando {len(texto_para_resumo)} caracteres para sumarização pela IA.")
                resumo_gerado = service.get_ai_response(prompt_resumo)
                messages.success(request, "Resumo gerado com sucesso!")
                logging.info(f"Resumo gerado para {pdf_file.name}.")

            except ValueError as e: # Erro na extração do PDF
                logging.error(f"Erro ao extrair texto do PDF para resumo: {e}", exc_info=True)
                messages.error(request, str(e))
            except ConfigurationError as e:
                logging.error(f"Erro de configuração do serviço de IA para resumo: {e}", exc_info=True)
                messages.error(request, f"Erro de configuração do sistema ao tentar resumir: {e}")
            except AIServiceError as e:
                logging.error(f"Erro no serviço de IA ao tentar resumir: {e}", exc_info=True)
                messages.error(request, f"Erro ao comunicar com o serviço de IA para resumo: {e}")
            except Exception as e:
                logging.error(f"Erro inesperado ao gerar resumo do PDF: {e}", exc_info=True)
                messages.error(request, f"Ocorreu um erro inesperado durante a geração do resumo: {e}")
        else:
            messages.error(request, "Houve um erro no formulário. Por favor, verifique os dados inseridos.")

    context.update({
        'form': form,
        'resumo_gerado': resumo_gerado
    })
    return render(request, 'generator/pdf_summary.html', context)
# --- FIM NOVA VIEW ---

