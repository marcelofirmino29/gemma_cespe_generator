# generator/views.py (VERSÃO REVISADA E CORRIGIDA COMPLETAMENTE)

from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import timezone
import logging
import datetime
from django.http import HttpResponse

# Importa TODOS os formulários necessários
from .forms import QuestionGeneratorForm, DiscursiveAnswerForm, DiscursiveExamForm
# Importa o serviço e as exceções necessárias
from .services import QuestionGenerationService
from .exceptions import (
    GeneratorError, ConfigurationError, AIServiceError,
    AIResponseError, ParsingError
)
# !!! Importe sua função de parsing aqui (ou defina-a) !!!
# from .utils import parse_evaluation_scores # Exemplo

logger = logging.getLogger('generator') # Use o logger padrão do app

# --- Função Auxiliar (Mantida - Sem alterações) ---
def _get_base_context_and_service():
    context = {}
    service = None
    service_initialized = True
    error_message = None
    try:
        service = QuestionGenerationService()
        logger.info(">>> QuestionGenerationService inicializado com sucesso na verificação.")
    except ConfigurationError as e:
        logger.critical(f">>> Falha CRÍTICA de configuração ao inicializar serviço: {e}", exc_info=False)
        error_message = f"Erro crítico de configuração interna do serviço: {e}. Verifique as configurações."
        service_initialized = False
    except Exception as e:
        logger.critical(f">>> Falha inesperada na inicialização do serviço: {e}", exc_info=True)
        error_message = f"Erro inesperado ao inicializar o serviço de IA: {e}"
        service_initialized = False

    context['service_initialized'] = service_initialized
    if error_message:
        context['error_message'] = error_message
    try:
        now_local = timezone.localtime(timezone.now())
        context['local_time'] = now_local.strftime('%d/%m/%Y %H:%M:%S %Z')
    except Exception as e_time:
        logger.error(f"Erro ao obter hora local: {e_time}")
        context['local_time'] = "N/A"

    return context, service if service_initialized else None, service_initialized

# --- VISÃO LANDING PAGE (Mantida - Sem alterações) ---
def landing_page_view(request):
    """Renderiza a página inicial com links para os modos de geração."""
    context, _, service_initialized = _get_base_context_and_service()
    # Garante que a mensagem de erro de inicialização seja passada, se houver
    context['error_message'] = context.get('error_message')
    return render(request, 'generator/landing_page.html', context)

# --- VISÃO GERADOR QUESTÕES C/E (REVISADA E CORRIGIDA) ---
def generate_questions_view(request):
    """Renderiza form e gera questões C/E baseadas em TÓPICO."""
    context, service, service_initialized = _get_base_context_and_service()
    generated_questions = None
    max_q = getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 5)
    form = QuestionGeneratorForm(request.POST or None, max_questions=max_q)
    context['form'] = form
    # Passa erro de inicialização para o contexto, se houver
    context['error_message'] = context.get('error_message')

    if request.method == 'POST':
        # Verifica se o serviço está ok *antes* de validar o form
        if not service_initialized or not service:
            logger.error("Tentativa de POST em generate_questions_view com serviço de IA inativo.")
            # Mantém a mensagem de erro de inicialização já presente no contexto
            context['error_message'] = context.get('error_message', "Serviço de IA indisponível.")
        else:
            logger.info("POST recebido: generate_questions_view (Questões C/E por Tópico)")
            if form.is_valid():
                # <<< CORREÇÃO: Use .get() e valide campos obrigatórios >>>
                topic_text = form.cleaned_data.get('topic')
                num_questions = form.cleaned_data.get('num_questions')
                difficulty = form.cleaned_data.get('difficulty_level')
                form_valid_for_api = True # Flag para controlar chamada à API

                # Validar campos que são logicamente obrigatórios para a API
                if not topic_text or not topic_text.strip():
                    form.add_error('topic', 'Este campo (Tópico) é obrigatório.')
                    form_valid_for_api = False
                if num_questions is None: # Inteiro não pode ser .strip()
                    form.add_error('num_questions', 'Este campo (Número de Questões) é obrigatório.')
                    form_valid_for_api = False
                if not difficulty or not difficulty.strip():
                     form.add_error('difficulty_level', 'Este campo (Nível de Dificuldade) é obrigatório.')
                     form_valid_for_api = False

                if not form_valid_for_api:
                    logger.warning(">>> Tentativa de Geração Q C/E (Tópico) com campo obrigatório ausente ou inválido (após is_valid).")
                    context['error_message'] = "Erro no formulário: Verifique os campos obrigatórios."
                else:
                    # Se todos os campos necessários existem, prossegue
                    logger.info(f">>> Form Q C/E válido para API. Solicitando {num_questions}q [{difficulty}] para TÓPICO: '{topic_text[:80]}...'")
                    try:
                        logger.debug(f"Tópico recebido: {topic_text}")
                        generated_questions = service.generate_questions(
                            topic=topic_text,
                            num_questions=num_questions,
                            difficulty_level=difficulty
                        )
                        if not generated_questions:
                            logger.warning(">>> Serviço Q C/E (Tópico) retornou uma lista vazia ou None.")
                            context['error_message'] = "A IA não retornou questões válidas ou formatadas corretamente a partir do tópico."
                        else:
                            logger.info(f">>> Questões C/E (Tópico) geradas pela IA: {len(generated_questions)}.")
                            context['error_message'] = None # Limpa erro se sucesso
                    except (AIResponseError, ParsingError, AIServiceError, GeneratorError, ConfigurationError, Exception) as e:
                        logger.error(f"Erro durante a geração de questões C/E (Tópico): {e}", exc_info=True)
                        context['error_message'] = f"Falha ao gerar questões a partir do tópico: {e}"
            else:
                # Formulário inválido pelas validações do Django
                logger.warning(">>> Tentativa de Geração Q C/E (Tópico) com formulário inválido (validação Django).")
                context['error_message'] = "Formulário inválido. Por favor, corrija os erros indicados."
                # Não precisa extrair o erro específico, o template deve mostrar os erros do form

    context['questions'] = generated_questions
    logger.debug(f"Contexto final (generate_questions_view): { {k: v for k, v in context.items() if k not in ['questions', 'form']} }")
    return render(request, 'generator/question_generator.html', context)


# --- VISÃO VALIDAR RESPOSTAS C/E (REVISADA - Lógica Principal Mantida) ---
def validate_answers_view(request):
    """Processa respostas C/E enviadas e calcula desempenho."""
    # Esta view não depende da inicialização do serviço de IA para sua lógica principal
    context, _, _ = _get_base_context_and_service() # Pega contexto base (hora local, etc)
    performance_data = None; results_list = []; error_processing = None
    # Adiciona um form vazio para o template, caso necessário (ex: exibir novamente com erro)
    context['form'] = QuestionGeneratorForm(max_questions=getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 5))

    if request.method == 'POST':
        logger.info("POST recebido: validate_answers_view")
        try:
            items_to_process = {}
            # Usa .get() para segurança ao buscar dados do POST
            all_post_keys = request.POST.keys()
            indices = sorted(list(set([int(k.split('_')[1]) for k in all_post_keys if k.startswith('index_')])))

            if not indices:
                raise ValueError("Nenhum item de questão (índice) encontrado nos dados do POST.")

            for index in indices:
                user_answer = request.POST.get(f'resposta_{index}')
                affirmation = request.POST.get(f'afirmacao_{index}')
                correct_answer = request.POST.get(f'gabarito_{index}')
                justification = request.POST.get(f'justificativa_{index}', 'Justificativa não disponível.') # Padrão se ausente

                # Validações básicas dos dados recebidos
                if user_answer is None or user_answer.strip().upper() not in ['C', 'E']:
                    logger.warning(f"Índice {index}: Resposta inválida ou ausente ('{user_answer}'). Ignorado."); continue
                if affirmation is None or not affirmation.strip():
                    logger.warning(f"Índice {index}: Afirmação vazia ou ausente. Ignorado."); continue
                if correct_answer is None or correct_answer.strip().upper() not in ['C', 'E']:
                    logger.warning(f"Índice {index}: Gabarito inválido ou ausente ('{correct_answer}'). Ignorado."); continue
                if not isinstance(justification, str): # Checa tipo, caso algo estranho seja enviado
                    logger.warning(f"Índice {index}: Justificativa em formato inválido (Tipo: {type(justification)})."); justification = 'Formato inválido.'

                is_correct = (user_answer.strip().upper() == correct_answer.strip().upper())
                items_to_process[index] = {
                    'index': index,
                    'afirmacao': affirmation.strip(),
                    'user_answer': user_answer.strip().upper(),
                    'gabarito': correct_answer.strip().upper(),
                    'correct': is_correct,
                    'justificativa': justification.strip()
                 }

            results_list = [items_to_process[i] for i in indices if i in items_to_process]

            if not results_list:
                error_processing = "Nenhum item válido encontrado para processar."
            else:
                 logger.info(f"Processados {len(results_list)} itens para validação.")
                 correct_count = sum(1 for r in results_list if r.get('correct'))
                 incorrect_count = len(results_list) - correct_count
                 total_questions = len(results_list)

                 # Cálculo da pontuação CESPE
                 final_score = correct_count - incorrect_count
                 percentage_correct = round((correct_count / total_questions) * 100) if total_questions > 0 else 0
                 # Performance pode ser definida de várias formas, exemplo: score > metade do total
                 more_than_half_score = (final_score > (total_questions / 2.0)) if total_questions > 0 else False

                 performance_data = {
                     'correct': correct_count,
                     'incorrect': incorrect_count,
                     'total': total_questions,
                     'score': final_score,
                     'percentage': percentage_correct,
                     'more_than_half': more_than_half_score # Exemplo de métrica
                 }
                 logger.info(f"Desempenho: {correct_count} C, {incorrect_count} E. Score: {final_score}/{total_questions}.")

        except ValueError as e:
            logger.error(f"Erro de valor ao processar validação: {e}", exc_info=True)
            error_processing = f"Erro nos dados recebidos: {e}."
        except Exception as e:
            logger.exception(f"Erro inesperado durante a validação das respostas: {e}")
            error_processing = "Ocorreu um erro inesperado ao processar as respostas."

        context['results'] = results_list
        if performance_data:
            context['performance'] = performance_data
        if error_processing:
            context['error_message'] = error_processing # Erro específico do processamento

        logger.debug(f"Contexto final (validate_answers_view): { {k: v for k, v in context.items() if k not in ['results', 'performance', 'form']} }")
        # Renderiza a mesma página (ou outra de resultados)
        return render(request, 'generator/question_generator.html', context) # Ou uma página de resultados específica

    elif request.method == 'GET':
        # GET não faz sentido aqui, redireciona para landing page
        logger.warning("GET recebido em validate_answers_view, redirecionando.")
        return redirect('landing_page')

    # Se não for POST nem GET (improvável), ou outro erro
    context['error_message'] = context.get('error_message', "Acesso inválido à página de validação.")
    return render(request, 'generator/question_generator.html', context)


# --- VISÃO GERAR RESPOSTA DISCURSIVA (REVISADA E CORRIGIDA) ---
def generate_discursive_view(request):
    """Renderiza form e gera resposta discursiva modelo."""
    context, service, service_initialized = _get_base_context_and_service()
    essay_answer = None
    form = DiscursiveAnswerForm(request.POST or None)
    context['form'] = form
    context['error_message'] = context.get('error_message') # Passa erro de inicialização

    if request.method == 'POST':
        if not service_initialized or not service:
            logger.error("POST generate_discursive_view com serviço IA inativo.")
            context['error_message'] = context.get('error_message', "Serviço IA indisponível.")
        else:
            logger.info("POST recebido: generate_discursive_view")
            if form.is_valid():
                # <<< CORREÇÃO: Use .get() e valide campo obrigatório >>>
                essay_prompt = form.cleaned_data.get('essay_prompt')
                key_points = form.cleaned_data.get('key_points') # Opcional
                limit = form.cleaned_data.get('limit') # Opcional
                area = form.cleaned_data.get('area') # Opcional
                form_valid_for_api = True

                if not essay_prompt or not essay_prompt.strip():
                    form.add_error('essay_prompt', 'Este campo (Comando da Questão) é obrigatório.')
                    form_valid_for_api = False

                if not form_valid_for_api:
                    logger.warning(">>> Tentativa Geração R. Discursiva com campo obrigatório ausente.")
                    context['error_message'] = "Erro no formulário: Verifique os campos obrigatórios."
                else:
                    logger.info(f">>> Form Gerar R. Discursiva válido para API. Prompt: '{essay_prompt[:80]}...'")
                    try:
                        essay_answer = service.generate_discursive_answer(
                            essay_prompt=essay_prompt,
                            key_points=key_points,
                            limit=limit,
                            area=area
                        )
                        logger.info(">>> Resposta discursiva modelo gerada pela IA.")
                        context['error_message'] = None # Limpa erro se sucesso
                    except (AIResponseError, AIServiceError, GeneratorError, ConfigurationError, Exception) as e:
                        logger.error(f"Erro gerar R. Discursiva: {e}", exc_info=True)
                        context['error_message'] = f"Falha ao gerar resposta: {e}"
            else:
                logger.warning(">>> Tentativa Geração R. Discursiva form inválido (validação Django).")
                context['error_message'] = "Formulário inválido. Corrija os erros."
        # Fim do bloco if service_initialized
    # Fim do bloco if request.method == 'POST'

    context['essay_answer'] = essay_answer
    logger.debug(f"Contexto final (generate_discursive_view): { {k: v for k, v in context.items() if k not in ['essay_answer', 'form']} }")
    return render(request, 'generator/discursive_generator.html', context)


# --- VISÃO GERAR QUESTÃO DISCURSIVA (REVISADA - JÁ CORRIGIDA ANTES) ---
def generate_discursive_exam_view(request):
    """Renderiza form e gera questão discursiva estruturada."""
    context, service, service_initialized = _get_base_context_and_service()
    discursive_exam_text = None
    form = DiscursiveExamForm(request.POST or None)
    context['form'] = form
    context['error_message'] = context.get('error_message') # Passa erro de inicialização

    if request.method == 'POST':
        if not service_initialized or not service:
            logger.error("POST generate_discursive_exam_view com serviço IA inativo.")
            context['error_message'] = context.get('error_message', "Serviço IA indisponível.")
        else:
            logger.info("POST recebido: generate_discursive_exam_view")
            if form.is_valid():
                # <<< REVISÃO: Acesso seguro já implementado na correção anterior >>>
                base_topic_or_context = form.cleaned_data.get('base_topic_or_context')
                num_aspects = form.cleaned_data.get('num_aspects', 3) # Opcional com padrão
                area = form.cleaned_data.get('area') # Opcional
                complexity = form.cleaned_data.get('complexity', 'Intermediária') # Opcional com padrão
                form_valid_for_api = True

                # Validar campo obrigatório
                if not base_topic_or_context or not base_topic_or_context.strip():
                    form.add_error('base_topic_or_context', 'Este campo (Tópico Base ou Contexto) é obrigatório.')
                    form_valid_for_api = False

                if not form_valid_for_api:
                    logger.warning(">>> Tentativa Geração Q. Discursiva sem 'base_topic_or_context'.")
                    context['error_message'] = "Erro no formulário: Verifique os campos obrigatórios."
                else:
                    logger.info(f">>> Form Gerar Q. Disc. válido para API. Tópico: '{base_topic_or_context[:80]}...'")
                    try:
                        discursive_exam_text = service.generate_discursive_exam_question(
                            base_topic_or_context=base_topic_or_context,
                            num_aspects=num_aspects,
                            area=area,
                            complexity=complexity
                        )
                        logger.info(">>> Estrutura questão discursiva gerada pela IA.")
                        context['error_message'] = None # Limpa erro se sucesso
                    except (AIResponseError, AIServiceError, GeneratorError, ParsingError, ConfigurationError, Exception) as e:
                        logger.error(f"Erro gerar Q. Discursiva: {e}", exc_info=True)
                        context['error_message'] = f"Falha ao gerar questão: {e}"
            else:
                logger.warning(">>> Tentativa Geração Q. Discursiva form inválido (validação Django).")
                context['error_message'] = "Formulário inválido. Corrija os erros."
        # Fim do bloco if service_initialized
    # Fim do bloco if request.method == 'POST'

    context['discursive_exam_text'] = discursive_exam_text
    logger.debug(f"Contexto final (generate_discursive_exam_view): { {k: v for k, v in context.items() if k not in ['discursive_exam_text', 'form']} }")
    return render(request, 'generator/discursive_exam_generator.html', context)


# --- VIEW PARA AVALIAR RESPOSTA DISCURSIVA (REVISADA COM ESTRUTURA DE PARSING) ---
def evaluate_discursive_answer_view(request):
    """Recebe resposta discursiva e contexto, chama IA para avaliação e tenta fazer parse do resultado."""
    context, service, service_initialized = _get_base_context_and_service()
    evaluation_result_text = None; evaluation_error = None
    submitted_exam_context = None; submitted_user_answer = None
    parsed_scores = None # Dicionário para guardar notas parseadas

    # Geralmente não se usa o form da questão aqui, talvez um form simples para a resposta?
    # Por enquanto, deixaremos sem form específico no GET, mas ele é criado no contexto base.
    context['form'] = DiscursiveExamForm() # Reutiliza um form, ajuste se necessário
    context['error_message'] = context.get('error_message') # Passa erro inicialização

    if request.method == 'POST':
        logger.info("POST recebido: evaluate_discursive_answer_view")
        # <<< CORREÇÃO: Use .get() para pegar dados do POST >>>
        user_answer = request.POST.get('user_answer', '').strip()
        exam_context = request.POST.get('exam_context', '').strip()
        line_count = request.POST.get('line_count', '0').strip() # Pega como string

        # Guarda os dados submetidos para re-exibir no template
        submitted_exam_context = exam_context
        submitted_user_answer = user_answer

        # Validações iniciais
        if not service_initialized or not service:
            logger.error("POST evaluate_discursive_answer_view com serviço IA inativo.")
            evaluation_error = context.get('error_message', "Serviço IA indisponível.")
        elif not user_answer:
            logger.warning("Avaliação sem resposta do usuário.")
            evaluation_error = "A resposta do usuário não foi fornecida."
        elif not exam_context:
            logger.warning("Avaliação sem contexto da questão.")
            evaluation_error = "O contexto/comando da questão não foi fornecido."
        else:
            # Se dados básicos estão presentes e serviço ok, tenta avaliar
            logger.info(f"Dados recebidos p/ avaliação. Resp: {len(user_answer)}, Contexto: {len(exam_context)}, Linhas: {line_count}")
            try:
                logger.info(">>> CHAMANDO service.evaluate_discursive_answer <<<")
                evaluation_result_text = service.evaluate_discursive_answer(
                    exam_context=exam_context,
                    user_answer=user_answer,
                    line_count=line_count
                )
                logger.info("Avaliação textual recebida do serviço.")
                context['error_message'] = None # Limpa erro se IA funcionou

                # --- <<< ESTRUTURA PARA PARSING >>> ---
                if evaluation_result_text:
                    try:
                        logger.info(">>> Tentando fazer o PARSE do resultado da avaliação...")
                        # !!! SUBSTITUA PELA SUA FUNÇÃO DE PARSING REAL !!!
                        # Exemplo: parsed_scores = _parse_evaluation_result(evaluation_result_text)
                        # Exemplo: from .utils import parse_evaluation_scores
                        # parsed_scores = parse_evaluation_scores(evaluation_result_text)
                        # --- Exemplo Placeholder ---
                        def _placeholder_parse_function(text):
                            # Simula extração - IMPLEMENTE SUA LÓGICA AQUI
                            scores = {'NC': None, 'NE': None, 'NPD': None, 'Comentários': 'Parsing não implementado.'}
                            if "NC:" in text: scores['NC'] = "Valor NC" # Exemplo
                            if "NE:" in text: scores['NE'] = "Valor NE" # Exemplo
                            if "NPD:" in text: scores['NPD'] = "Valor NPD" # Exemplo
                            logger.warning("Usando função de parsing placeholder. IMPLEMENTE A SUA!")
                            return scores
                        parsed_scores = _placeholder_parse_function(evaluation_result_text)
                        # --- Fim Exemplo Placeholder ---
                        logger.info(f">>> Resultado do Parsing: {parsed_scores}")

                    except (ParsingError, ValueError, Exception) as parse_error:
                        logger.error(f"Erro ao fazer o PARSE do resultado da avaliação: {parse_error}", exc_info=True)
                        evaluation_error = f"Erro ao processar o resultado da avaliação: {parse_error}. Resultado bruto exibido."
                        parsed_scores = None # Garante que não há scores parseados se erro
                # --- <<< FIM ESTRUTURA PARSING >>> ---

            except (AIResponseError, AIServiceError, GeneratorError, ConfigurationError, Exception) as e:
                 logger.error(f"Erro ao chamar o serviço de avaliação discursiva: {e}", exc_info=True)
                 evaluation_error = f"Erro na comunicação com o serviço de IA durante a avaliação: {e}"
                 evaluation_result_text = None # Garante que não há texto se erro da IA
        # Fim do bloco else (dados básicos ok e serviço ok)
    # Fim do bloco if request.method == 'POST'

    elif request.method == 'GET':
        logger.warning("GET recebido em evaluate_discursive_answer_view, redirecionando.")
        # Redireciona para a página de gerar questão discursiva ou landing page
        return redirect('generate_discursive_exam') # Ou 'landing_page'

    # Atualiza o contexto com os resultados (ou erros)
    context['evaluation_result_text'] = evaluation_result_text # Texto bruto da IA
    context['evaluation_error'] = evaluation_error # Mensagem de erro (se houver)
    context['submitted_exam_context'] = submitted_exam_context # Para reexibir
    context['submitted_user_answer'] = submitted_user_answer # Para reexibir
    context['parsed_scores'] = parsed_scores # Notas parseadas (ou None)

    logger.debug(f"Contexto final (evaluate_discursive_answer_view): { {k: v for k, v in context.items() if k not in ['submitted_user_answer', 'submitted_exam_context', 'form', 'evaluation_result_text']} }")
    return render(request, 'generator/discursive_evaluation_result.html', context)
# --- FIM VIEW AVALIAÇÃO ---


# --- Função de Teste (Mantida - Sem alterações) ---
def test_print_view(request):
    """View simples para teste rápido de print e log no console."""
    message = f">>> TESTE PRINT VIEW EXECUTADO em {datetime.datetime.now()} <<<"
    print(message)
    logger.info(">>> Log INFO da test_print_view (via logger do app 'generator')")
    logger.warning(">>> Log WARNING da test_print_view")
    return HttpResponse(f"<h1>Teste Concluído</h1><p>{message}</p><p>Verifique o console/terminal onde o servidor Django está rodando para ver o print e os logs.</p>")