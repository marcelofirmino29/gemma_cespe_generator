# generator/services.py - VERSÃO ALTERADA PARA GERAR Afirmação/Gabarito C/E

import logging
from django.conf import settings
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from .exceptions import ConfigurationError, AIServiceError, AIResponseError, ParsingError

logger = logging.getLogger('generator')

class QuestionGenerationService:
    def __init__(self):
        self.model = None
        self.generation_config = None
        self.safety_settings = None # Inicializa o atributo

        try:
            # --- Configuração da API Key ---
            api_key = settings.GOOGLE_API_KEY
            if not api_key:
                raise ConfigurationError("GOOGLE_API_KEY não definida nas configurações do Django.")
            genai.configure(api_key=api_key)

            # --- Configuração de Geração ---
            self.generation_config = genai.types.GenerationConfig(
                temperature=settings.AI_GENERATION_TEMPERATURE
                # Adicione outros parâmetros de Geração aqui se necessário
            )

            # --- Inicialização do Modelo ---
            self.model = genai.GenerativeModel(
                 settings.AI_MODEL_NAME,
                 # Passe generation_config aqui se desejar usá-lo sempre
                 # generation_config=self.generation_config
            )
            logger.info(f"Modelo Generative AI '{settings.AI_MODEL_NAME}' inicializado (Init do Service).")

            # --- Carrega e Converte Configurações de Segurança ---
            self._load_and_convert_safety_settings() # Carrega do settings.py

        except AttributeError as e:
             # Pega erro se faltar GOOGLE_API_KEY, AI_MODEL_NAME, etc no settings.py
             raise ConfigurationError(f"Configuração ausente em settings.py: {e}")
        except ConfigurationError as e: # Pega o raise explícito de 'if not api_key:'
             raise e
        except Exception as e:
            # Pega outros erros potenciais durante a configuração do genai
            logger.critical(f"Falha inesperada ao inicializar o cliente Google AI: {e}", exc_info=True)
            raise ConfigurationError(f"Falha inesperada ao inicializar o cliente Google AI: {e}")

    def _load_and_convert_safety_settings(self):
        """Carrega as configurações de segurança do settings.py e converte strings para enums."""
        raw_settings = getattr(settings, 'GOOGLE_AI_SAFETY_SETTINGS', None)
        if not raw_settings or not isinstance(raw_settings, list):
            logger.warning("GOOGLE_AI_SAFETY_SETTINGS não definidas, vazias ou inválidas em settings.py. Usando padrões da API.")
            self.safety_settings = None # API usará padrões
            return

        converted_settings = []
        # Mapeamento para converter strings de volta para Enums
        category_map = {name: member for name, member in HarmCategory.__members__.items()}
        threshold_map = {name: member for name, member in HarmBlockThreshold.__members__.items()}

        try:
            for setting in raw_settings:
                if not isinstance(setting, dict):
                    logger.warning(f"Item inválido encontrado em GOOGLE_AI_SAFETY_SETTINGS (não é dicionário): {setting}")
                    continue

                category_str = setting.get("category")
                threshold_str = setting.get("threshold")

                category_enum = category_map.get(category_str)
                threshold_enum = threshold_map.get(threshold_str)

                if category_enum is None:
                     raise ConfigurationError(f"Valor inválido para 'category' em GOOGLE_AI_SAFETY_SETTINGS: '{category_str}'")
                if threshold_enum is None:
                     raise ConfigurationError(f"Valor inválido para 'threshold' em GOOGLE_AI_SAFETY_SETTINGS: '{threshold_str}'")

                converted_settings.append({
                    "category": category_enum,
                    "threshold": threshold_enum
                })

            if converted_settings: # Só atribui se converteu pelo menos um
                 self.safety_settings = converted_settings
                 logger.info(f"Configurações de segurança carregadas e convertidas de settings.py: {self.safety_settings}")
            else:
                 logger.warning("Nenhuma configuração de segurança válida encontrada após processar GOOGLE_AI_SAFETY_SETTINGS.")
                 self.safety_settings = None # Usa padrões da API

        except Exception as e:
             logger.error(f"Erro ao processar GOOGLE_AI_SAFETY_SETTINGS: {e}", exc_info=True)
             # É mais seguro levantar um erro aqui do que usar padrões inesperados
             raise ConfigurationError(f"Erro ao processar GOOGLE_AI_SAFETY_SETTINGS: {e}")

    # --- MÉTODO generate_questions ALTERADO ---
    def generate_questions(self, topic, num_questions):
        """Gera afirmações estilo C/E com gabarito usando a API do Google AI."""
        if not self.model:
            raise ConfigurationError("Serviço de IA não inicializado corretamente.")

        # NOVO PROMPT - Pede afirmações C/E e gabarito no formato especificado
        # Pede um separador "---" para ajudar o parsing
        prompt = (
            f"Gere {num_questions} afirmações sobre o tópico principal: '{topic}'. "
            f"Cada afirmação deve ser no estilo CERTO/ERRADO (como as da banca Cespe/Cebraspe), "
            f"sendo claramente verdadeira (Certo) ou falsa (Errado). "
            f"Para cada afirmação, forneça o gabarito (C ou E). "
            f"Use o formato EXATO abaixo para cada item, separando os itens com '---':\n"
            f"Afirmação: [O texto da afirmação aqui]\n"
            f"Gabarito: [C ou E]\n"
            f"---"
        )

        # Usa as safety_settings carregadas do settings.py (armazenadas em self.safety_settings)
        logger.info(f"SERVICE CALL (C/E): Usando safety_settings carregadas: {self.safety_settings}")

        try:
            logger.info(f"Enviando requisição (C/E) para API (Modelo: {settings.AI_MODEL_NAME}, Tópico: {topic[:50]}...)")
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config, # Passa config de geração (temp, etc)
                safety_settings=self.safety_settings # <<< USA AS CONFIGS CARREGADAS DO __init__
            )

            # Verifica se a resposta foi bloqueada
            if not response.candidates:
                 block_reason = "Razão não especificada"
                 block_reason_message = ""
                 ratings_message = ""
                 # Tenta obter detalhes do bloqueio se disponíveis
                 if response.prompt_feedback:
                      if response.prompt_feedback.block_reason:
                           block_reason = response.prompt_feedback.block_reason.name
                           block_reason_message = response.prompt_feedback.block_reason_message or ""
                      ratings_message = str(response.prompt_feedback.safety_ratings)

                 logger.warning(f"Resposta da IA bloqueada (C/E). Razão: {block_reason}. Mensagem: '{block_reason_message}'. Ratings: {ratings_message}")
                 # Lança um erro específico que a view pode tratar
                 raise AIResponseError(f"A geração foi bloqueada pela API (Razão: {block_reason}). {block_reason_message}")

            # Se não foi bloqueado, processa o texto
            generated_text = response.text
            # Chama o método de parsing interno (que agora extrai afirmação e gabarito)
            parsed_questions = self._parse_questions(generated_text) # Chama o NOVO parser abaixo
            return parsed_questions

        except AIResponseError as e:
            # Relança o erro de bloqueio já tratado
            raise e
        except Exception as e:
            # Pega outros erros da API ou de comunicação
            logger.error(f"Erro na chamada da API Google AI (C/E): {e}", exc_info=True)
            # Verifica se o erro genérico menciona segurança/bloqueio
            if "safety" in str(e).lower() or "blocked" in str(e).lower():
                 raise AIResponseError(f"A geração foi bloqueada pela API (C/E - erro geral): {e}")
            else: # Senão, assume erro de comunicação/serviço
                 raise AIServiceError(f"Erro na comunicação com a API Google AI (C/E): {e}")
    # --- FIM DO MÉTODO generate_questions ALTERADO ---


    # --- MÉTODO _parse_questions ALTERADO ---
    def _parse_questions(self, text: str) -> list:
        """
        Faz o parsing do texto bruto da IA para extrair uma lista de dicionários
        contendo 'afirmacao' e 'gabarito' (C/E).
        Espera o formato:
        Afirmação: [Texto]
        Gabarito: [C ou E]
        --- (opcional)
        """
        if not text:
            logger.warning("Texto recebido para parsing (C/E) está vazio.")
            return []

        logger.debug(f"Texto recebido para parsing (C/E): >>>\n{text}\n<<<")
        structured_questions = []
        current_affirmation = None
        current_gabarito = None

        lines = text.strip().split('\n')
        try:
            for line_num, line in enumerate(lines): # Adiciona número da linha para logs
                cleaned_line = line.strip()

                if not cleaned_line: # Ignora linhas vazias
                    continue

                # Normaliza possíveis variações no início da linha e verifica
                if cleaned_line.upper().startswith("AFIRMAÇÃO:"):
                    # Se já tínhamos um item completo, salva antes de começar o novo
                    if current_affirmation is not None and current_gabarito is not None:
                        structured_questions.append({'afirmacao': current_affirmation, 'gabarito': current_gabarito})
                        logger.debug(f"Item (C/E) parseado e adicionado (antes da linha {line_num+1}): Afirmação='{current_affirmation[:50]}...', Gabarito='{current_gabarito}'")
                    # Inicia uma nova afirmação, pegando o texto após "Afirmação:"
                    current_affirmation = cleaned_line[len("Afirmação:"):].strip()
                    current_gabarito = None # Reseta o gabarito
                    logger.debug(f"Linha {line_num+1}: Nova afirmação iniciada: '{current_affirmation[:50]}...'")

                elif cleaned_line.upper().startswith("GABARITO:") and current_affirmation is not None:
                    # Só processa gabarito se temos uma afirmação esperando por ele
                    gabarito_text = cleaned_line[len("Gabarito:"):].strip().upper()
                    if gabarito_text in ['C', 'E']:
                        current_gabarito = gabarito_text
                        logger.debug(f"Linha {line_num+1}: Gabarito '{current_gabarito}' encontrado para afirmação atual.")
                    else:
                        logger.warning(f"Linha {line_num+1}: Gabarito inválido ('{gabarito_text}') encontrado para afirmação: '{current_affirmation[:100]}...' - Item será ignorado.")
                        # Descarta a afirmação atual se o gabarito for inválido
                        current_affirmation = None
                        current_gabarito = None

                elif cleaned_line == "---":
                     # Se encontrou o separador e tinha um item completo, salva
                     if current_affirmation is not None and current_gabarito is not None:
                          structured_questions.append({'afirmacao': current_affirmation, 'gabarito': current_gabarito})
                          logger.debug(f"Item (C/E) parseado e adicionado (via '---' na linha {line_num+1}): Afirmação='{current_affirmation[:50]}...', Gabarito='{current_gabarito}'")
                     # Reseta para o próximo bloco, independentemente de ter salvo ou não
                     current_affirmation = None
                     current_gabarito = None
                     logger.debug(f"Linha {line_num+1}: Separador '---' encontrado, resetando item atual.")

                elif current_affirmation is not None and current_gabarito is None:
                    # Considera continuação da afirmação (multi-linhas)
                    # Só adiciona se não for uma linha que deveria ser Gabarito mas foi inválida
                    current_affirmation += " " + cleaned_line
                    logger.debug(f"Linha {line_num+1}: Adicionada à afirmação multi-linha: '{cleaned_line}'")
                elif cleaned_line: # Linha não vazia que não se encaixa em nenhum padrão esperado
                     logger.warning(f"Linha {line_num+1}: Texto inesperado ignorado durante parsing C/E: '{cleaned_line}'")


            # Adiciona o último item se ele estiver completo após o loop terminar
            if current_affirmation is not None and current_gabarito is not None:
                structured_questions.append({'afirmacao': current_affirmation, 'gabarito': current_gabarito})
                logger.debug(f"Último item (C/E) parseado e adicionado após loop: Afirmação='{current_affirmation[:50]}...', Gabarito='{current_gabarito}'")

        except Exception as e:
            logger.error(f"Erro durante o parsing C/E do texto: {e}\nTexto Parcialmente Processado: {structured_questions}\nTexto Original: {text}", exc_info=True)
            # Retorna o que conseguiu processar em caso de erro no meio
            return structured_questions

        logger.info(f"Resultado ESTRUTURADO FINAL (Afirmação/Gabarito) - {len(structured_questions)} itens: {structured_questions}")
        if not structured_questions and text:
             logger.warning(f"Não foi possível fazer o parsing C/E de nenhum item formatado do texto: '{text[:200]}...'")

        return structured_questions
    # --- FIM DO MÉTODO _parse_questions ALTERADO ---

# Nenhum código solto deve existir depois do fim da classe QuestionGenerationService neste arquivo.