from collections import Counter
import json
import re
from venv import logger

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from generator.exceptions import AIResponseError, AIServiceError
from generator.forms import AskAIForm, QuestionGeneratorForm
from generator.models import Avaliacao, Questao, TentativaResposta
from generator.utils import STOP_WORDS_PT
from generator.views.views_generate_questions import _get_base_context_and_service
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone

def landing_page_view(request):
    """Renderiza a página inicial, incluindo dados para a nuvem de palavras extraídos das questões."""
    context, _, service_initialized = _get_base_context_and_service()
    context['error_message'] = context.get('error_message') # Pega erro da inicialização do serviço, se houver

    # --- Lógica para buscar palavras das Questões para a Nuvem ---
    word_cloud_data = [] # Lista vazia por padrão
    try:
        # 1. Buscar textos das questões recentes (ajuste o limite conforme necessário)
        # Considera questões C/E e Discursivas. Pega os últimos 100, por exemplo.
        questoes_recentes = Questao.objects.order_by('-criado_em')[:100]
        textos_combinados = ""
        for q in questoes_recentes:
            if q.texto_motivador:
                textos_combinados += q.texto_motivador + " "
            if q.texto_comando:
                textos_combinados += q.texto_comando + " "
            # Adicionar 'justificativa_gabarito' ou 'aspectos_discursiva' se relevante
            # if q.justificativa_gabarito:
            #     textos_combinados += q.justificativa_gabarito + " "

        if not textos_combinados:
            logger.info("Nenhum texto encontrado nas questões recentes para gerar nuvem de palavras.")

        else:
            # 2. Limpar e Tokenizar o texto
            # Converte para minúsculas, remove pontuação básica (exceto hífens internos), e divide em palavras
            textos_combinados = textos_combinados.lower()
            # Remove pontuações comuns, mantendo hífens e acentos por enquanto
            textos_combinados = re.sub(r'[.,!?;:()\[\]"\'“”‘’`]', ' ', textos_combinados)
            # Remove múltiplos espaços
            textos_combinados = re.sub(r'\s+', ' ', textos_combinados).strip()
            # Divide em palavras
            palavras = textos_combinados.split(' ')

            # 3. Filtrar stop words e palavras curtas/numéricas
            palavras_filtradas = [
                palavra for palavra in palavras
                if palavra not in STOP_WORDS_PT and len(palavra) > 2 and not palavra.isdigit()
            ]

            if not palavras_filtradas:
                 logger.info("Nenhuma palavra relevante encontrada após filtragem para a nuvem.")
            else:
                # 4. Contar frequência
                contagem = Counter(palavras_filtradas)

                # 5. Pegar as N palavras mais comuns (ex: 50 mais comuns)
                num_palavras_nuvem = 50
                palavras_mais_comuns = contagem.most_common(num_palavras_nuvem)

                # A nuvem espera apenas a lista de palavras (strings)
                word_cloud_data = [palavra for palavra, freq in palavras_mais_comuns]
                logger.info(f"Extraídas {len(word_cloud_data)} palavras das questões para a nuvem.")

    except Exception as e:
        # Captura erros gerais durante o processo
        logger.error(f"Erro ao processar textos das questões para nuvem: {e}", exc_info=True)
        word_cloud_data = ["Erro", "processar", "palavras"] # Fallback

    # Adiciona a lista de palavras (ou fallback) ao contexto
    context['word_cloud_data'] = word_cloud_data
    # --------------------------------------------------------

    # Renderiza o template da landing page com o contexto atualizado
    return render(request, 'generator/landing_page.html', context)


# --- VISÃO VALIDAR RESPOSTAS C/E (SALVA TENTATIVA E AVALIAÇÃO) ---
@login_required
def validate_answers_view(request):
    context, _, _ = _get_base_context_and_service()
    performance_data = None; results_list = []; error_processing = None
    # Passa um form vazio para o contexto caso precise re-renderizar a página base
    context['form'] = QuestionGeneratorForm(max_questions=getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 150)) # Ajuste max_questions se necessário

    if request.method == 'POST':
        logger.info(f"POST validate_answers_view por {request.user.username}")
        try:
            all_post_keys = request.POST.keys()
            # Pega todos os índices/IDs presentes no POST que iniciam com 'questao_id_'
            # Usaremos os IDs diretamente, assumindo que o name do input é 'resposta_q{questao.id}'
            questao_ids_respondidas = [k.split('_')[-1] for k in all_post_keys if k.startswith('resposta_q')]

            if not questao_ids_respondidas:
                 # Tenta a forma antiga se a nova falhar (fallback)
                 questao_ids_respondidas = [request.POST.get(f'questao_id_{i}') for i in sorted(list(set([int(k.split('_')[-1]) for k in all_post_keys if k.startswith('questao_id_')]))) if request.POST.get(f'questao_id_{i}')]
                 if not questao_ids_respondidas:
                     raise ValueError("Nenhum ID de questão encontrado no POST (nem 'resposta_qID' nem 'questao_id_X').")

            logger.info(f"IDs das questões recebidas para validação: {questao_ids_respondidas}")

            attempt_results = [] # Guarda resultados para exibir no template
            total_processed = 0; correct_count = 0; incorrect_count = 0

            for questao_id in questao_ids_respondidas:
                # Pega a resposta usando o ID da questão
                user_answer = request.POST.get(f'resposta_q{questao_id}')

                # Validações básicas dos dados recebidos do form
                if user_answer is None or user_answer.strip().upper() not in ['C', 'E']:
                    logger.warning(f"Questão ID {questao_id}: Resposta inválida/ausente ('{user_answer}'). Pulando.")
                    error_processing = (error_processing or "") + f" Erro: Resposta inválida para questão ID {questao_id}."
                    continue # Pula para o próximo ID

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
                        'questao_id': questao_obj.id, # Passa o ID para referência
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
                    logger.error(f"Questão C/E ID {questao_id} não encontrada no DB. Pulando.")
                    error_processing = (error_processing or "") + f" Erro: Questão ID {questao_id} não encontrada."
                except Exception as db_error:
                    logger.error(f"Erro DB ao processar item (Questao ID {questao_id}): {db_error}", exc_info=True)
                    error_processing = (error_processing or "") + f" Erro ao salvar/processar questão ID {questao_id}."

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

        except ValueError as e:
            logger.error(f"Erro ValueError ao processar validação: {e}", exc_info=True)
            error_processing = f"Erro nos dados recebidos: {e}."
        except Exception as e:
            logger.exception(f"Erro Exception inesperado na validação: {e}")
            error_processing = "Erro inesperado durante o processamento das respostas."

        # Passa os resultados e performance para o contexto
        context['results'] = results_list
        if performance_data:
            context['performance'] = performance_data
        if error_processing:
            context['error_message'] = error_processing # Adiciona ou sobrescreve erro

        logger.debug(f"Contexto final (validate_answers_view POST): User={request.user.username}, { {k: v for k, v in context.items() if k not in ['results', 'performance', 'form']} }")
        # Renderiza a mesma página, agora mostrando os resultados
        return render(request, 'generator/question_generator.html', context)

    elif request.method == 'GET':
        # Se alguém tentar acessar a URL de validação via GET, redireciona
        logger.warning(f"Tentativa de acesso GET a validate_answers_view por {request.user.username or 'Anônimo'}")
        messages.info(request, "Para gerar questões, use o formulário abaixo.")
        return redirect('generator:generate_questions') # Redireciona para a página de gerar questões

    # Caso algo muito estranho aconteça (nem GET nem POST?)
    context['error_message'] = context.get('error_message', "Acesso inválido.")
    return render(request, 'generator/question_generator.html', context)

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

# --- VIEW: Pergunte à IA (MODIFICADA para aceitar GET param e auto-submit) ---
@login_required
def ask_ai_view(request):
    """
    Exibe um formulário para o usuário fazer uma pergunta, mostra a resposta da IA.
    Aceita um parâmetro GET 'question' para pré-preencher e submeter automaticamente.
    """
    context, service, service_initialized = _get_base_context_and_service()
    ai_response = None
    user_question = None
    form = None # Inicializa form como None

    # --- Lógica GET: Verifica se veio pergunta da URL ---
    if request.method == 'GET':
        question_from_url = request.GET.get('question')
        if question_from_url:
            user_question = question_from_url # Guarda a pergunta para exibir
            logger.info(f"User '{request.user.username}' acessou AskAI com pergunta da URL: '{user_question[:100]}...'")

            # Tenta obter a resposta da IA imediatamente
            if service_initialized and service:
                try:
                    ai_response = service.get_ai_response(user_question)
                    logger.info("Resposta da IA (AskAI - GET) recebida com sucesso.")
                    # Não exibe mensagem de sucesso aqui, pois foi automático
                except AttributeError:
                     logger.error(f"Método 'get_ai_response' não encontrado no serviço {type(service).__name__}.")
                     messages.error(request, "Erro interno: Funcionalidade de pergunta genérica não implementada no serviço.")
                     ai_response = "Erro: Funcionalidade indisponível."
                except (AIResponseError, AIServiceError) as e:
                    logger.error(f"Erro ao obter resposta da IA (AskAI - GET): {e}", exc_info=True)
                    messages.error(request, f"Erro ao comunicar com a IA: {e}")
                    ai_response = f"Erro ao obter resposta: {e}"
                except Exception as e:
                    logger.error(f"Erro inesperado ao obter resposta da IA (AskAI - GET): {e}", exc_info=True)
                    messages.error(request, "Ocorreu um erro inesperado ao processar sua pergunta.")
                    ai_response = "Erro inesperado no servidor."
            else: # Serviço não inicializado
                messages.error(request, "Serviço de IA indisponível no momento.")
                ai_response = "Serviço indisponível."

            # Cria o formulário pré-preenchido com a pergunta da URL
            form = AskAIForm(initial={'user_question': user_question})

        else: # GET normal, sem parâmetro
             form = AskAIForm() # Cria um formulário vazio

    # --- Lógica POST: Submissão manual pelo formulário ---
    elif request.method == 'POST':
        form = AskAIForm(request.POST)
        if form.is_valid():
            user_question = form.cleaned_data['user_question']
            logger.info(f"User '{request.user.username}' perguntou (AskAI - POST): '{user_question[:100]}...'")

            if service_initialized and service:
                try:
                    ai_response = service.get_ai_response(user_question)
                    logger.info("Resposta da IA (AskAI - POST) recebida com sucesso.")
                    messages.success(request, "Resposta da IA recebida.")
                    # Limpa o formulário após sucesso para nova pergunta
                    form = AskAIForm() # Cria um novo form vazio
                except AttributeError:
                     logger.error(f"Método 'get_ai_response' não encontrado no serviço {type(service).__name__}.")
                     messages.error(request, "Erro interno: Funcionalidade de pergunta genérica não implementada no serviço.")
                     ai_response = "Erro: Funcionalidade indisponível."
                     # Mantém o form preenchido
                except (AIResponseError, AIServiceError) as e:
                    logger.error(f"Erro ao obter resposta da IA (AskAI - POST): {e}", exc_info=True)
                    messages.error(request, f"Erro ao comunicar com a IA: {e}")
                    ai_response = f"Erro ao obter resposta: {e}" # Exibe o erro da IA
                    # Mantém o form preenchido com a pergunta que deu erro
                except Exception as e:
                    logger.error(f"Erro inesperado ao obter resposta da IA (AskAI - POST): {e}", exc_info=True)
                    messages.error(request, "Ocorreu um erro inesperado ao processar sua pergunta.")
                    ai_response = "Erro inesperado no servidor."
                    # Mantém o form preenchido
            else: # Serviço não inicializado
                messages.error(request, "Serviço de IA indisponível no momento.")
                ai_response = "Serviço indisponível."
                # Mantém o form preenchido
        else: # Form inválido
            logger.warning(f"Formulário 'Pergunte à IA' inválido por {request.user.username}: {form.errors.as_json()}")
            # O form com erros será passado para o contexto abaixo
            messages.error(request, "Por favor, corrija os erros no formulário.")

    # Garante que o form sempre exista no contexto
    if form is None:
        form = AskAIForm()

    context['form'] = form
    context['ai_response'] = ai_response # Resposta da IA ou mensagem de erro
    context['user_question'] = user_question # Passa a pergunta feita para exibição (ou None em GET sem param)

    return render(request, 'generator/ask_ai.html', context)
# --- FIM VIEW AskAI ---
