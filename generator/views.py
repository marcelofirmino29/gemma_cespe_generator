# generator/views.py

from django.shortcuts import render, redirect, reverse, get_object_or_404 
from django.urls import reverse 
from urllib.parse import urlencode   
from django.conf import settings
from django.utils import timezone
import logging
import datetime
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from datetime import datetime
from django.views.decorators.http import require_POST
import json
import re # Para expressões regulares (limpeza de texto)
from collections import Counter # Para contar frequência de palavras
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import requests # <<< GARANTA ESTE IMPORT
import json     # <<< GARANTA ESTE IMPORT (para JSONDecodeError)
import PyPDF2 # Exemplo de biblioteca para extração de texto

from .forms import PDFUploadForm
# Importa Formulários
from .forms import (
    QuestionGeneratorForm, DiscursiveAnswerForm, DiscursiveExamForm, AskAIForm,
    AreaConhecimentoForm, CustomUserCreationForm, SimuladoConfigForm
)
# Importa Serviço e Exceções
from .services import QuestionGenerationService
from .exceptions import (
    GeneratorError, ConfigurationError, AIServiceError, AIResponseError, ParsingError
)
# Importa Parser e Models
from .utils import parse_evaluation_scores
# Remove a importação de PalavraChave se não for mais usada em outras views
from .models import Questao, AreaConhecimento, TentativaResposta, Avaliacao
from django.db.models import Q

logger = logging.getLogger('generator')

# --- Lista de Stop Words (Português) ---
# (Pode ser expandida ou movida para um arquivo/setting separado)
STOP_WORDS_PT = set([
    'a', 'à', 'adeus', 'agora', 'aí', 'ainda', 'além', 'algo', 'alguém', 'algum', 'alguma', 'algumas', 'alguns', 'ali',
    'ampla', 'amplas', 'amplo', 'amplos', 'ano', 'anos', 'ante', 'antes', 'ao', 'aos', 'apenas', 'apoio', 'após', 'aquela',
    'aquelas', 'aquele', 'aqueles', 'aqui', 'aquilo', 'área', 'as', 'às', 'assim', 'até', 'atrás', 'através', 'baixo',
    'bastante', 'bem', 'boa', 'boas', 'bom', 'bons', 'breve', 'cá', 'cada', 'catorze', 'cedo', 'cento', 'certamente',
    'certeza', 'cima', 'cinco', 'coisa', 'coisas', 'com', 'como', 'conselho', 'contra', 'contudo', 'custa', 'da', 'dá',
    'dão', 'daquela', 'daquelas', 'daquele', 'daqueles', 'dar', 'das', 'de', 'debaixo', 'dela', 'delas', 'dele', 'deles',
    'demais', 'dentro', 'depois', 'desde', 'dessa', 'dessas', 'desse', 'desses', 'desta', 'destas', 'deste', 'destes',
    'deve', 'devem', 'devendo', 'dever', 'deverá', 'deverão', 'deveria', 'deveriam', 'devia', 'deviam', 'dez', 'dezanove',
    'dezasseis', 'dezassete', 'dezoito', 'dia', 'diante', 'disse', 'disso', 'disto', 'dito', 'diz', 'dizem', 'dizer', 'do',
    'dois', 'dos', 'doze', 'duas', 'dúvida', 'e', 'é', 'ela', 'elas', 'ele', 'eles', 'em', 'embora', 'enquanto', 'entre',
    'era', 'eram', 'éramos', 'és', 'essa', 'essas', 'esse', 'esses', 'esta', 'está', 'estamos', 'estão', 'estar', 'estas',
    'estás', 'estava', 'estavam', 'estávamos', 'este', 'esteja', 'estejam', 'estejamos', 'estes', 'esteve', 'estive',
    'estivemos', 'estiver', 'estivera', 'estiveram', 'estivéramos', 'estiverem', 'estivermos', 'estivesse', 'estivessem',
    'estivéssemos', 'estiveste', 'estivestes', 'estou', 'etc', 'eu', 'exemplo', 'faço', 'falta', 'favor', 'faz', 'fazeis',
    'fazem', 'fazemos', 'fazer', 'fazes', 'fazia', 'façamos', 'fez', 'fim', 'final', 'foi', 'fomos', 'for', 'fora', 'foram',
    'fôramos', 'forem', 'formos', 'fosse', 'fossem', 'fôssemos', 'foste', 'fostes', 'fui', 'geral', 'grande', 'grandes',
    'grupo', 'há', 'haja', 'hajam', 'hajamos', 'havemos', 'havia', 'hei', 'hoje', 'hora', 'horas', 'houve', 'houvemos',
    'houver', 'houvera', 'houverá', 'houveram', 'houvéramos', 'houverão', 'houverei', 'houverem', 'houveremos', 'houveria',
    'houveriam', 'houveríamos', 'houvermos', 'houvesse', 'houvessem', 'houvéssemos', 'isso', 'isto', 'já', 'la', 'lá',
    'lado', 'lhe', 'lhes', 'lo', 'local', 'logo', 'longe', 'lugar', 'maior', 'maioria', 'mais', 'mal', 'mas', 'máximo',
    'me', 'meio', 'menor', 'menos', 'mês', 'meses', 'mesma', 'mesmas', 'mesmo', 'mesmos', 'meu', 'meus', 'mil', 'minha',
    'minhas', 'momento', 'muita', 'muitas', 'muito', 'muitos', 'na', 'nada', 'não', 'naquela', 'naquelas', 'naquele',
    'naqueles', 'nas', 'nem', 'nenhum', 'nenhuma', 'nessa', 'nessas', 'nesse', 'nesses', 'nesta', 'nestas', 'neste',
    'nestes', 'ninguém', 'nível', 'no', 'noite', 'nome', 'nos', 'nós', 'nossa', 'nossas', 'nosso', 'nossos', 'nova',
    'novas', 'nove', 'novo', 'novos', 'num', 'numa', 'número', 'nunca', 'o', 'obra', 'obrigada', 'obrigado', 'oitava',
    'oitavo', 'oito', 'onde', 'ontem', 'onze', 'os', 'ou', 'outra', 'outras', 'outro', 'outros', 'para', 'parece', 'parte',
    'partir', 'paucas', 'pela', 'pelas', 'pelo', 'pelos', 'pequena', 'pequenas', 'pequeno', 'pequenos', 'per', 'perante',
    'perto', 'pode', 'pude', 'pôde', 'podem', 'podendo', 'poder', 'poderia', 'poderiam', 'podia', 'podiam', 'põe', 'põem',
    'pois', 'ponto', 'pontos', 'por', 'porém', 'porque', 'porquê', 'posição', 'possível', 'possivelmente', 'posso', 'pouca',
    'poucas', 'pouco', 'poucos', 'primeira', 'primeiras', 'primeiro', 'primeiros', 'própria', 'próprias', 'próprio',
    'próprios', 'próxima', 'próximas', 'próximo', 'próximos', 'pude', 'puderam', 'quais', 'quáis', 'qual', 'quando',
    'quanto', 'quantos', 'quarta', 'quarto', 'quatro', 'que', 'quê', 'quem', 'quer', 'quereis', 'querem', 'queremas',
    'queres', 'quero', 'questão', 'quinta', 'quinto', 'quinze', 'relação', 'sabe', 'sabem', 'são', 'se', 'segunda',
    'segundo', 'sei', 'seis', 'seja', 'sejam', 'sejamos', 'sem', 'sempre', 'sendo', 'ser', 'será', 'serão', 'serei',
    'seremos', 'seria', 'seriam', 'seríamos', 'sete', 'sétima', 'sétimo', 'seu', 'seus', 'si', 'sido', 'sim', 'sistema',
    'só', 'sob', 'sobre', 'sois', 'somos', 'sou', 'sua', 'suas', 'tal', 'talvez', 'também', 'tampouco', 'tanta', 'tantas',
    'tanto', 'tão', 'tarde', 'te', 'tem', 'tém', 'têm', 'temos', 'tendes', 'tendo', 'tenha', 'tenham', 'tenhamos', 'tenho',
    'tens', 'ter', 'terá', 'terão', 'terceira', 'terceiro', 'terei', 'teremos', 'teria', 'teriam', 'teríamos', 'teu',
    'teus', 'teve', 'ti', 'tido', 'tinha', 'tinham', 'tínhamos', 'tive', 'tivemos', 'tiver', 'tivera', 'tiveram',
    'tivéramos', 'tiverem', 'tivermos', 'tivesse', 'tivessem', 'tivéssemos', 'tiveste', 'tivestes', 'toda', 'todas',
    'todavia', 'todo', 'todos', 'trabalho', 'três', 'treze', 'tu', 'tua', 'tuas', 'tudo', 'última', 'últimas', 'último',
    'últimos', 'um', 'uma', 'umas', 'uns', 'vai', 'vais', 'vão', 'vários', 'vem', 'vêm', 'vendo', 'ver', 'vez', 'vezes',
    'viagem', 'vindo', 'vinte', 'vir', 'você', 'vocês', 'vos', 'vós', 'vossa', 'vossas', 'vosso', 'vossos', 'zero', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '_'
    # Adicionar palavras específicas do domínio que não agregam valor (ex: 'questão', 'item', 'certo', 'errado', 'julgue')
    'afirmativa', 'abaixo', 'acerca', 'acima', 'apresentado', 'aspecto', 'assertiva', 'assinale', 'comando', 'conforme',
    'contexto', 'correto', 'correta', 'errado', 'errada', 'exige', 'fragmento', 'hipotética', 'ilustra', 'item', 'itens',
    'julgue', 'marque', 'opção', 'proposição', 'questão', 'seguinte', 'seguintes', 'situação', 'texto', 'tópico', 'trecho',
    'verdadeiro', 'falso', 'cebraspe'
])


# --- Função Auxiliar ---
def _get_base_context_and_service():
    """Inicializa o serviço de IA e obtém o contexto base."""
    context = {}
    service = None
    service_initialized = True
    error_message = None
    try:
        service = QuestionGenerationService()
        logger.info(">>> Service inicializado.")
    except ConfigurationError as e:
        logger.critical(f">>> Falha config: {e}", exc_info=False)
        error_message = f"Erro config: {e}."
        service_initialized = False
    except Exception as e:
        logger.critical(f">>> Falha inesperada init: {e}", exc_info=True)
        error_message = f"Erro inesperado init IA: {e}"
        service_initialized = False

    context['service_initialized'] = service_initialized
    if error_message:
        context['error_message'] = error_message

    try:
        now_local = timezone.localtime(timezone.now())
        context['local_time'] = now_local.strftime('%d/%m/%Y %H:%M:%S %Z')
    except Exception:
        context['local_time'] = "N/A"

    return context, service if service_initialized else None, service_initialized

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


# --- VISÃO LANDING PAGE (PÚBLICA) ---
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

# --- VISÃO CADASTRO (PÚBLICA) ---
def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            logger.info(f"Novo usuário cadastrado: {username}")
            messages.success(request, f'Conta criada com sucesso para {username}! Você já pode fazer login.')
            return redirect('login') # Redireciona para a página de login
        else:
            logger.warning(f"Falha no cadastro de usuário: {form.errors.as_json()}")
            # Os erros do formulário serão exibidos no template
    else: # GET request
        form = CustomUserCreationForm()
    context = {'form': form}
    return render(request, 'generator/register.html', context)

logger = logging.getLogger(__name__)

# --- FUNÇÃO REAL PARA EXTRAIR TEXTO COMPLETO DO PDF usando PyPDF2 ---
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


# --- Sua função _get_base_context_and_service ---
def _get_base_context_and_service(): # Mantenha sua implementação real
    context = {}
    service = None 
    service_initialized = True 
    try:
        context['all_areas'] = AreaConhecimento.objects.all().order_by('nome')
    except Exception as e:
        logger.error(f"Erro ao carregar todas as áreas: {e}")
        context['all_areas'] = []
    if not service_initialized:
        context['error_message'] = "Serviço de IA indisponível."
    if service_initialized: # Simulação do serviço de IA (SUBSTITUA PELO SEU SERVIÇO REAL)
        class MockAIService:
            def generate_questions(self, topic, num_questions, difficulty_level):
                logger.info(f"MockAIService: Chamado para gerar {num_questions}q para o tópico/contexto fornecido (dif: {difficulty_level}). Início do contexto: '{topic[:100]}...'")
                items = []
                for i in range(num_questions):
                    items.append({
                        'afirmacao': f'Afirmação REALMENTE GERADA PELA IA #{i+1} com base no contexto (dificuldade: {difficulty_level}).',
                        'gabarito': 'C' if i % 2 == 0 else 'E',
                        'justificativa': f'Justificativa real para o item {i+1} baseada no contexto.'
                    })
                return f"Texto motivador principal REAL para o contexto: '{topic[:70]}...'", items
        service = MockAIService()
    return context, service, service_initialized
# --- Fim da simulação ---

@login_required
def generate_questions_view(request):
    base_context, service, service_initialized = _get_base_context_and_service()
    context = base_context.copy() 
    context['service_initialized'] = service_initialized
    
    max_q = getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 150)
    
    # Inicializa form para GET e como base para POST com erros
    form_instance = QuestionGeneratorForm(max_questions=max_q)
    context['page_obj'] = None
    context['paginator'] = None
    context['main_motivador'] = None

    if request.method == 'POST':
        logger.info(f"POST generate_questions_view por {request.user.username}")
        request.session.pop('latest_ce_ids', None)
        request.session.pop('latest_ce_motivador', None)

        form_instance = QuestionGeneratorForm(request.POST, request.FILES, max_questions=max_q)
        
        pdf_file_uploaded = False
        if 'pdf_contexto' in request.FILES and request.FILES.get('pdf_contexto'):
            pdf_file_uploaded = True
            logger.info(f"Arquivo PDF '{request.FILES['pdf_contexto'].name}' foi detectado no POST.")

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
                    # ***** USANDO A FUNÇÃO DE EXTRAÇÃO DE TEXTO COMPLETO DO PDF *****
                    contexto_para_ia = extrair_texto_completo_pdf(pdf_file_cleaned)
                    fonte_contexto = f"PDF: {pdf_file_cleaned.name}"
                    
                    if not contexto_para_ia.strip():
                        messages.error(request, f"Não foi possível extrair conteúdo textual útil do PDF '{pdf_file_cleaned.name}'. O arquivo pode ser uma imagem, estar protegido, ser muito complexo ou estar vazio. Tente o contexto textual.")
                        return render(request, 'generator/question_generator.html', context)
                    logger.info(f"Contexto para IA obtido do PDF: '{pdf_file_cleaned.name}' ({len(contexto_para_ia)} caracteres). Início: '{contexto_para_ia[:250]}...'")

                except ValueError as ve: 
                    messages.error(request, str(ve)) # Erro vindo da função de extração
                    return render(request, 'generator/question_generator.html', context)
                except Exception as e_pdf_extract: 
                    logger.error(f"Erro crítico ao extrair texto do PDF '{pdf_file_cleaned.name}': {e_pdf_extract}", exc_info=True)
                    messages.error(request, "Ocorreu um erro inesperado ao tentar ler o arquivo PDF.")
                    return render(request, 'generator/question_generator.html', context)
            elif topic_text_cleaned:
                contexto_para_ia = topic_text_cleaned
                fonte_contexto = "Tópico Textual"
                logger.info(f"Usando contexto do campo Tópico ({len(contexto_para_ia)} caracteres). Início: '{contexto_para_ia[:250]}...'")
            
            if not contexto_para_ia.strip(): # Checagem final do contexto antes de enviar para IA
                messages.error(request, "Contexto para IA está vazio. Forneça um tópico ou PDF com conteúdo legível.")
                return render(request, 'generator/question_generator.html', context)

            logger.info(f"Preparando para chamar IA. Fonte: {fonte_contexto}. Num Questões: {num_questions}. Dificuldade: {difficulty}.")
            try:
                main_motivador, generated_items_data = service.generate_questions(
                    topic=contexto_para_ia, 
                    num_questions=num_questions, 
                    difficulty_level=difficulty
                )
                # ... (Sua lógica de salvar questões na sessão, etc. continua aqui) ...
                if not generated_items_data or not isinstance(generated_items_data, list):
                    messages.warning(request,"IA retornou dados inválidos."); generated_items_data = []
                saved_question_ids = []
                if generated_items_data:
                    logger.info(f"Salvando {len(generated_items_data)} itens...")
                    for item_data in generated_items_data:
                        try:
                            if not isinstance(item_data, dict): continue
                            gabarito = item_data.get('gabarito'); afirmacao = item_data.get('afirmacao')
                            if not gabarito or gabarito not in ['C', 'E'] or not afirmacao or not afirmacao.strip(): continue
                            q = Questao(tipo='CE', texto_motivador=main_motivador, texto_comando=afirmacao, gabarito_ce=gabarito, justificativa_gabarito=item_data.get('justificativa'), dificuldade=(difficulty or 'medio'), area=area_obj, criado_por=request.user)
                            q.save(); saved_question_ids.append(q.id)
                        except Exception as save_error: logger.error(f"Erro salvar C/E item: {save_error}", exc_info=True)
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
                logger.error(f"Erro INESPERADO na Geração ou Salvamento C/E: {e}", exc_info=True)
                context['error_message'] = f"Erro inesperado: {e}"
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
        
        if latest_ids:
            logger.info(f"GET: IDs encontrados na sessão para paginação: {latest_ids}.")
            try:
                question_list = Questao.objects.filter(id__in=latest_ids).select_related('area', 'criado_por').order_by('id')
                logger.info(f"GET: Número de questões encontradas no DB: {question_list.count()}")

                if question_list.exists():
                    items_per_page = getattr(settings, 'ITEMS_PER_PAGE_GENERATOR', 20)
                    paginator = Paginator(question_list, items_per_page) 
                    logger.info(f"GET: Paginator. Total de itens: {paginator.count}, Total de páginas: {paginator.num_pages}")

                    page_number = request.GET.get('page')
                    try:
                        page_obj = paginator.get_page(page_number)
                    except PageNotAnInteger:
                        page_obj = paginator.get_page(1)
                    except EmptyPage:
                        page_obj = paginator.get_page(paginator.num_pages)
                    
                    context['page_obj'] = page_obj
                    context['paginator'] = paginator
                    
                    logger.info(f"GET: Paginação configurada. Página: {page_obj.number} de {paginator.num_pages}.")
                else:
                    logger.warning(f"GET: IDs {latest_ids} na sessão, mas NENHUMA questão encontrada. Limpando sessão.")
                    request.session.pop('latest_ce_ids', None); request.session.pop('latest_ce_motivador', None)
                    context['main_motivador'] = None 
            except Exception as e:
                logger.error(f"GET: Erro ao buscar/paginar questões da sessão: {e}", exc_info=True)
                messages.error(request, "Erro ao carregar ou paginar as questões da sessão.")
                request.session.pop('latest_ce_ids', None); request.session.pop('latest_ce_motivador', None)
                context['main_motivador'] = None
        else:
            logger.info("GET: Nenhum 'latest_ce_ids' encontrado na sessão.")
            context['main_motivador'] = None
            context['page_obj'] = None # Garante que page_obj seja None se não houver latest_ids
            context['paginator'] = None # Garante que paginator seja None se não houver latest_ids
        
    return render(request, 'generator/question_generator.html', context)

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


logger = logging.getLogger('generator')

# Função auxiliar _get_base_context_and_service (mantenha a sua)
def _get_base_context_and_service(): # Exemplo básico
    context = {}
    service = None
    service_initialized = True
    try: service = QuestionGenerationService()
    except Exception as e: logger.error(f"Falha Service Init: {e}"); context['error_message'] = f"Erro IA: {e}"; service_initialized = False
    context['service_initialized'] = service_initialized
    return context, service, service_initialized


logger = logging.getLogger(__name__)


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


# --- VIEW Realização do Simulado ---
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


# --- VISÃO DASHBOARD (COM FILTRO DE DATA) ---
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
    area_filter_id = request.GET.get('area_filter') # Novo filtro de área

    # Converte datas string para objetos date
    if date_from_str:
        try: date_from_obj = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError: messages.warning(request, "Formato de data inicial inválido. Use AAAA-MM-DD."); date_from_obj = None
    if date_to_str:
        try: date_to_obj = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError: messages.warning(request, "Formato de data final inválido. Use AAAA-MM-DD."); date_to_obj = None

    area_filter_obj = None
    if area_filter_id:
        try: area_filter_obj = AreaConhecimento.objects.get(id=area_filter_id)
        except (AreaConhecimento.DoesNotExist, ValueError): messages.warning(request, "Área selecionada inválida."); area_filter_obj = None

    logger.info(f"Dashboard acessado por {request.user.username}. Filtros: Data=({date_from_str} a {date_to_str}), AreaID={area_filter_id}")

    try:
        # Busca base de TODAS as tentativas do usuário
        todas_tentativas_qs = TentativaResposta.objects.filter(
            usuario=request.user
        ).select_related( # Otimiza busca de dados relacionados
            'questao', 'questao__area'
        ).prefetch_related( # Otimiza busca reversa OneToOne
            'avaliacao'
        )

        # --- Aplica Filtros ---
        if date_from_obj:
            todas_tentativas_qs = todas_tentativas_qs.filter(data_resposta__date__gte=date_from_obj)
        if date_to_obj:
            # Adiciona 1 dia ao date_to para incluir o dia inteiro
            date_to_inclusive = date_to_obj + datetime.timedelta(days=1)
            todas_tentativas_qs = todas_tentativas_qs.filter(data_resposta__lt=date_to_inclusive) # Usa __lt com dia seguinte
        if area_filter_obj:
             todas_tentativas_qs = todas_tentativas_qs.filter(questao__area=area_filter_obj)

        # --- Cálculos (sobre o queryset filtrado) ---
        total_geral_filtrado = todas_tentativas_qs.count() # Total no período/área

        # Filtra C/E DENTRO do queryset já filtrado para estatísticas
        tentativas_ce_filtradas = todas_tentativas_qs.filter(questao__tipo='CE')
        total_ce_filtrado = tentativas_ce_filtradas.count()
        acertos_ce = 0; erros_ce = 0
        for t_ce in tentativas_ce_filtradas: # Itera SOMENTE nas C/E filtradas
            avaliacao = getattr(t_ce, 'avaliacao', None) # Pega do prefetch
            if avaliacao and avaliacao.correto_ce is not None: # Verifica se tem avaliação e se C/E foi avaliado
                if avaliacao.correto_ce: acertos_ce += 1
                else: erros_ce += 1
        score_ce = acertos_ce - erros_ce
        percentual_ce = round((acertos_ce / total_ce_filtrado) * 100) if total_ce_filtrado > 0 else 0

        # Filtra Discursivas DENTRO do queryset já filtrado
        tentativas_disc_filtradas = todas_tentativas_qs.filter(questao__tipo='DISC')
        total_disc_filtrado = tentativas_disc_filtradas.count()
        nc_total = 0.0; ne_total = 0; npd_total = 0.0; count_disc_avaliadas = 0
        for t_disc in tentativas_disc_filtradas:
             avaliacao = getattr(t_disc, 'avaliacao', None)
             # Soma apenas se a avaliação discursiva foi feita e tem notas válidas
             if avaliacao and avaliacao.nc is not None and avaliacao.ne is not None and avaliacao.npd is not None:
                  nc_total += avaliacao.nc
                  ne_total += avaliacao.ne
                  npd_total += avaliacao.npd
                  count_disc_avaliadas += 1
        # Médias Discursivas (calculadas apenas sobre as avaliadas no período/área)
        media_nc = round(nc_total / count_disc_avaliadas, 2) if count_disc_avaliadas > 0 else None
        media_ne = round(ne_total / count_disc_avaliadas, 2) if count_disc_avaliadas > 0 else None # NE é contagem, média pode não fazer sentido
        media_npd = round(npd_total / count_disc_avaliadas, 2) if count_disc_avaliadas > 0 else None


        stats = {
            'total_geral': total_geral_filtrado, # Total no período/área
            'total_ce': total_ce_filtrado,
            'acertos_ce': acertos_ce,
            'erros_ce': erros_ce,
            'score_ce': score_ce,
            'percentual_ce': percentual_ce,
            'total_disc': total_disc_filtrado,
            'total_disc_avaliadas': count_disc_avaliadas, # Quantas foram efetivamente avaliadas pela IA
            'media_nc': media_nc,
            'media_ne': media_ne, # Média de erros de português
            'media_npd': media_npd, # Média da nota final discursiva
        }
        logger.info(f"Stats Dashboard (Filtrado) {request.user.username}: {stats}")

        # Pega as últimas 20 DENTRO do período/área filtrado para exibir na lista
        tentativas_recentes = todas_tentativas_qs.order_by('-data_resposta')[:20]

    except Exception as e:
        logger.error(f"Erro ao carregar dados do dashboard para {request.user.username}: {e}", exc_info=True)
        messages.error(request, "Ocorreu um erro ao carregar seu desempenho. Tente novamente mais tarde.")
        tentativas_recentes = []
        stats = {}

    context['tentativas_list'] = tentativas_recentes
    context['stats'] = stats
    # Passa os filtros usados de volta para o template preencher o form
    context['current_date_from'] = date_from_obj
    context['current_date_to'] = date_to_obj
    context['current_area_filter'] = area_filter_obj # Passa o objeto Area
    context['all_areas'] = AreaConhecimento.objects.all().order_by('nome') # Passa todas as áreas para o dropdown do filtro

    return render(request, 'generator/dashboard.html', context)


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


# --- VIEW PARA O HUB DE JOGOS ---
@login_required
def games_hub_view(request):
    """Renderiza a página que lista os jogos disponíveis."""
    context, _, _ = _get_base_context_and_service()
    available_games = [
        {
            'name': 'Arrastar e Soltar: Algoritmos ML',
            'description': 'Associe algoritmos como SVM, KNN e K-Means às suas categorias.',
            'url_name': 'generator:drag_drop_ml_game', # Nome da URL definida em urls.py
            'icon': 'bi-arrows-move' # Classe do ícone Bootstrap Icons
        },
        {
             'name': 'Caça-Palavras: Termos LGPD',
             'description': 'Encontre termos importantes da Lei Geral de Proteção de Dados.',
             'url_name': 'generator:word_search_lgpd_game',
             'icon': 'bi-search'
        },
         {
             'name': 'Aprendendo JS com Blocos',
             'description': 'Uma introdução interativa à lógica de programação JavaScript.',
             'url_name': 'generator:scratch_js_game',
             'icon': 'bi-puzzle-fill'
         },
        # Adicione mais jogos aqui conforme são criados
    ]
    context['games'] = available_games
    # Aponta para o template do hub de jogos
    return render(request, 'generator/jogos/games_hub.html', context)

# --- VIEW PARA O JOGO DE ARRASTAR E SOLTAR ML ---
@login_required
def drag_drop_ml_game_view(request):
    """Renderiza a página do jogo de arrastar e soltar sobre algoritmos de ML."""
    context, _, _ = _get_base_context_and_service()
    # Aponta para o template específico do jogo
    return render(request, 'generator/jogos/game_drag_drop_ml.html', context)

# --- VIEW PARA O JOGO ESTILO SCRATCH JS ---
@login_required
def scratch_js_view(request):
    """Renderiza a página estilo Scratch para aprender JS."""
    context, _, _ = _get_base_context_and_service()
    # A lógica principal será no frontend (HTML/JS)
    return render(request, 'generator/jogos/scratch_js_learning.html', context)

# --- VIEW PARA O JOGO CAÇA-PALAVRAS LGPD ---
@login_required
def word_search_lgpd_view(request):
    """Renderiza a página do jogo de caça-palavras sobre LGPD."""
    context, _, _ = _get_base_context_and_service()
    return render(request, 'generator/jogos/game_word_search_lgpd.html', context)


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


# --- VIEWS PARA GERENCIAMENTO DE ÁREAS DE CONHECIMENTO ---
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
def add_area_view(request):
    """Exibe o formulário para adicionar uma nova Área e processa a submissão."""
    context, _, _ = _get_base_context_and_service()

    if request.method == 'POST':
        form = AreaConhecimentoForm(request.POST)
        if form.is_valid():
            try:
                nova_area = form.save(commit=False) # Cria o objeto mas não salva ainda
                # Poderia associar o usuário que criou, se quisesse:
                # nova_area.criado_por = request.user
                nova_area.save() # Salva no banco
                nome_area = form.cleaned_data.get('nome')
                messages.success(request, f"Área '{nome_area}' adicionada com sucesso!")
                logger.info(f"Nova Área de Conhecimento adicionada: '{nome_area}' por {request.user.username}")
                # Redireciona para a lista de áreas após salvar
                return redirect('generator:area_list')
            except Exception as e:
                 logger.error(f"Erro ao salvar nova Área de Conhecimento '{form.cleaned_data.get('nome')}': {e}", exc_info=True)
                 messages.error(request, "Erro ao salvar a nova área no banco de dados.")
                 # Mantém o form preenchido com os dados que deram erro
        else:
            # Se o form for inválido, ele será re-renderizado com os erros
            logger.warning(f"Tentativa inválida de adicionar Área por {request.user.username}: {form.errors.as_json()}")
            messages.error(request, "Erro ao adicionar área. Verifique os erros no formulário.")
    else: # GET request
        form = AreaConhecimentoForm() # Cria um formulário vazio

    context['form'] = form
    context['titulo_pagina'] = "Adicionar Nova Área de Conhecimento" # Título para o template
    # Reutiliza o template do formulário
    return render(request, 'generator/area_form.html', context)

# --- View para Adição Rápida de Área (vinda do Gerador C/E) ---
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


@login_required # Mantém o requisito de login, remova se o jogo for público
def aventura_dados_view(request):
    """
    Renderiza a página do jogo Aventura de Dados.
    """
    # Se precisar de contexto base (usuário, etc.), use a função auxiliar
    # context, _, _ = _get_base_context_and_service()
    # Se não precisar de contexto extra, pode usar um dicionário vazio:
    context = {}
    return render(request, 'generator/jogos/aventura_dados.html', context)

# --- Função de Teste (Mantida) ---
@login_required
def test_print_view(request):
    """View simples para testes rápidos de log e resposta."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f">>> TESTE PRINT VIEW EXECUTADO por {request.user.username} em {now_str} <<<"
    print(message) # Imprime no console onde o Django está rodando
    logger.info(f">>> Log INFO test_print_view (User: {request.user.username})")
    logger.warning(">>> Log WARNING test_print_view")
    logger.error(">>> Log ERROR test_print_view (apenas para teste)")
    # Retorna uma resposta HTTP simples para o navegador
    return HttpResponse(f"<h1>Teste Concluído</h1><p>{message}</p><p>Logado como: {request.user.username}</p><p>Verifique o console e os logs do Django.</p>")

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



logger = logging.getLogger('generator')

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

@login_required
def listar_concursos_view(request):
    context = {}
    concursos_list = []
    error_message = None
    api_base_url = "https://concursos-publicos-api.vercel.app/api"

    # --- Filtros ---
    filtro_titulo = request.GET.get('q', '').strip()
    filtro_estado = request.GET.get('estado', '').strip().upper()
    filtro_regiao = request.GET.get('regiao', '').strip().capitalize()

    # --- Monta URL ---
    api_url = api_base_url
    params = {} # Para futura expansão se a API aceitar query params

    if filtro_titulo:
        api_url = f"{api_base_url}/titulo/{filtro_titulo}"
        context['filtro_ativo'] = filtro_titulo
    elif filtro_estado:
        if len(filtro_estado) == 2 and filtro_estado.isalpha():
            api_url = f"{api_base_url}/estado/{filtro_estado}"
            context['filtro_ativo'] = f"Estado: {filtro_estado}"
        else:
            error_message = "Sigla de estado inválida."; api_url = None; filtro_estado = ''
    elif filtro_regiao:
        regioes_validas = ['Norte', 'Nordeste', 'Sul', 'Sudeste', 'Centro-oeste']
        api_filtro_regiao = next((r for r in regioes_validas if r.lower() == filtro_regiao.lower()), None)
        if api_filtro_regiao:
             # A API parece usar 'Centro-Oeste', ajuste se necessário
             api_url_regiao = 'Centro-Oeste' if api_filtro_regiao.lower() == 'centro-oeste' else api_filtro_regiao
             api_url = f"{api_base_url}/regiao/{api_url_regiao}"
             context['filtro_ativo'] = f"Região: {api_filtro_regiao}"
        else:
            error_message = "Região inválida."; api_url = None; filtro_regiao = ''
    else:
        # Busca Sudeste por padrão para não sobrecarregar
        api_url = f"{api_base_url}/regiao/Sudeste"
        context['filtro_ativo'] = "Região: Sudeste (padrão)"; filtro_regiao = 'Sudeste'

    # --- Chama API ---
    if api_url:
        try:
            logger.info(f"Chamando API externa de concursos: {api_url}")
            # VV CORREÇÃO 1: usar requests.get VV
            response = requests.get(api_url, timeout=15)
            response.raise_for_status()
            concursos_data = response.json()

            if isinstance(concursos_data, list):
                concursos_list = concursos_data
                logger.info(f"Recebidos {len(concursos_list)} concursos.")
            else:
                logger.warning(f"API retornou formato inesperado: {type(concursos_data)}")
                error_message = "API externa retornou dados em formato inesperado."

        # VV CORREÇÃO 2: usar requests.exceptions.Timeout VV
        except requests.exceptions.Timeout:
            logger.error(f"Timeout ao chamar API: {api_url}")
            error_message = "Busca por concursos demorou muito. Tente novamente."
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro conexão/HTTP API: {e}")
            error_message = f"Erro ao conectar com API de concursos: Verifique a URL ou a API pode estar offline."
        except json.JSONDecodeError:
            logger.error(f"Erro decodificar JSON API: {api_url}")
            error_message = "API externa retornou resposta inválida."
        except Exception as e:
            logger.error(f"Erro inesperado API concursos: {e}", exc_info=True)
            error_message = "Erro inesperado ao buscar concursos."

    # --- Paginação ---
    items_per_page = 15
    paginator = Paginator(concursos_list, items_per_page)
    page_number = request.GET.get('page')
    try: page_obj = paginator.get_page(page_number)
    except PageNotAnInteger: page_obj = paginator.get_page(1)
    except EmptyPage: page_obj = paginator.get_page(paginator.num_pages)

    # --- Contexto Final ---
    context['page_obj'] = page_obj
    context['paginator'] = paginator
    context['error_message'] = error_message
    context['filtro_titulo_atual'] = filtro_titulo
    context['filtro_estado_atual'] = filtro_estado
    context['filtro_regiao_atual'] = filtro_regiao
    context['regioes_validas'] = ['Norte', 'Nordeste', 'Sul', 'Sudeste', 'Centro-oeste']

    # Busca Areas para o filtro (se ainda não tiver)
    if 'all_areas' not in context: # Evita buscar se já veio de outra parte do contexto base
        try: context['all_areas'] = AreaConhecimento.objects.all().order_by('nome')
        except Exception as e: logger.error(f"Erro buscar AreaConhecimento: {e}")

    return render(request, 'generator/listar_concursos.html', context)

logger = logging.getLogger(__name__)

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
