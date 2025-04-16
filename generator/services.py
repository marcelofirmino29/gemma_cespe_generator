# generator/services.py

import logging
from django.conf import settings
import google.generativeai as genai
# Corrigido para importar HarmBlockThreshold corretamente
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
                # Usando getattr para segurança caso a setting não exista
                temperature=getattr(settings, 'AI_GENERATION_TEMPERATURE', 0.7) # Exemplo de default
                # Adicione outros parâmetros de Geração aqui se necessário
            )

            # --- Inicialização do Modelo ---
            model_name = getattr(settings, 'AI_MODEL_NAME', None)
            if not model_name:
                raise ConfigurationError("AI_MODEL_NAME não definida nas configurações do Django.")

            self.model = genai.GenerativeModel(
                 model_name,
                 # generation_config=self.generation_config # Pode ser passado aqui ou na chamada
            )
            logger.info(f"Modelo Generative AI '{model_name}' inicializado (Init do Service).")

            # --- Carrega e Converte Configurações de Segurança ---
            self._load_and_convert_safety_settings() # Carrega do settings.py

        except AttributeError as e:
             # Pega erro se faltar uma setting OBRIGATÓRIA como API key ou model name
             missing_setting = str(e).split("'")[-2] # Tenta extrair o nome da setting
             raise ConfigurationError(f"Configuração obrigatória ausente em settings.py: '{missing_setting}'")
        except ConfigurationError as e: # Pega os raises explícitos
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

                # Verifica se as chaves existem
                if category_str is None or threshold_str is None:
                    logger.warning(f"Dicionário incompleto em GOOGLE_AI_SAFETY_SETTINGS (falta 'category' ou 'threshold'): {setting}")
                    continue

                category_enum = category_map.get(category_str)
                threshold_enum = threshold_map.get(threshold_str)

                if category_enum is None:
                     # Log e continua para o próximo, em vez de falhar tudo
                     logger.error(f"Valor inválido para 'category' em GOOGLE_AI_SAFETY_SETTINGS: '{category_str}'. Pulando esta configuração.")
                     continue
                     # raise ConfigurationError(f"Valor inválido para 'category' em GOOGLE_AI_SAFETY_SETTINGS: '{category_str}'")
                if threshold_enum is None:
                     logger.error(f"Valor inválido para 'threshold' em GOOGLE_AI_SAFETY_SETTINGS: '{threshold_str}'. Pulando esta configuração.")
                     continue
                     # raise ConfigurationError(f"Valor inválido para 'threshold' em GOOGLE_AI_SAFETY_SETTINGS: '{threshold_str}'")

                converted_settings.append({
                    "category": category_enum,
                    "threshold": threshold_enum
                })

            if converted_settings: # Só atribui se converteu pelo menos um
                 self.safety_settings = converted_settings
                 logger.info(f"Configurações de segurança carregadas e convertidas de settings.py: {len(converted_settings)} regras.")
                 logger.debug(f"Detalhe Safety Settings: {self.safety_settings}")
            else:
                 logger.warning("Nenhuma configuração de segurança válida encontrada após processar GOOGLE_AI_SAFETY_SETTINGS.")
                 self.safety_settings = None # Usa padrões da API

        except Exception as e:
             logger.error(f"Erro inesperado ao processar GOOGLE_AI_SAFETY_SETTINGS: {e}", exc_info=True)
             # Levanta erro para alertar sobre falha na configuração de segurança
             raise ConfigurationError(f"Erro ao processar GOOGLE_AI_SAFETY_SETTINGS: {e}")

    # --- MÉTODO generate_questions ALTERADO ---
    # Adicionado 'difficulty_level' como parâmetro
    def generate_questions(self, topic, num_questions, difficulty_level='medio'):
        """Gera afirmações estilo C/E com gabarito usando a API do Google AI."""
        if not self.model:
            raise ConfigurationError("Serviço de IA não inicializado corretamente.")

        # --- MODIFICADO: Prompt inclui difficulty_level ---
        # Instruções mais claras sobre o formato e a dificuldade.
        prompt = (
            f"**Instrução Principal:** Gere {num_questions} itens para julgamento (estilo Certo/Errado - Cespe/Cebraspe) "
            f"sobre o tópico principal: '{topic}'.\n"
            f"**Nível de Dificuldade:** O nível de dificuldade desejado para os itens é '{difficulty_level}'.\n"
            f"**Formato OBRIGATÓRIO de Saída:**\n"
            f"Para CADA item gerado, use EXATAMENTE o formato abaixo. Separe cada item completo (Afirmação + Gabarito) com três hifens ('---').\n\n"
            f"Afirmação: [Texto da afirmação aqui. Deve ser claramente Certa ou Errada.]\n"
            f"Gabarito: [Use apenas 'C' para Certo ou 'E' para Errado]\n"
            f"---\n"
            f"Afirmação: [Texto da segunda afirmação...]\n"
            f"Gabarito: [C ou E]\n"
            f"---"
            f"\n(Continue o padrão para os {num_questions} itens solicitados)"
        )
        # --- FIM MODIFICAÇÃO ---

        # Usa as safety_settings carregadas do settings.py (armazenadas em self.safety_settings)
        if self.safety_settings:
            logger.info(f"SERVICE CALL (C/E): Usando {len(self.safety_settings)} regras de segurança carregadas.")
            logger.debug(f"Detalhe Safety Settings para chamada: {self.safety_settings}")
        else:
            logger.info("SERVICE CALL (C/E): Usando configurações de segurança padrão da API.")

        try:
            # --- MODIFICADO: Log inclui difficulty_level ---
            logger.info(f"Enviando requisição (C/E) para API (Modelo: {self.model._model_name}, Tópico: {topic[:50]}..., Dificuldade: {difficulty_level})")
            # --- FIM MODIFICAÇÃO ---

            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config, # Passa config de geração (temp, etc)
                safety_settings=self.safety_settings # Passa as configs de segurança (pode ser None)
            )

            # --- Verificação de Bloqueio (Melhorada) ---
            # Acessa o primeiro candidato se existir
            first_candidate = response.candidates[0] if response.candidates else None

            if first_candidate and first_candidate.finish_reason.name == 'SAFETY':
                 # Tenta obter detalhes do bloqueio a partir do primeiro candidato ou do prompt_feedback
                 block_reason = "SAFETY" # finish_reason indica bloqueio
                 block_reason_message = "A resposta foi bloqueada devido às configurações de segurança."
                 ratings_message = ""

                 # Tenta obter ratings do candidato (mais comum para bloqueio de *resposta*)
                 if first_candidate.safety_ratings:
                      ratings_message = ", ".join([f"{r.category.name}: {r.probability.name}" for r in first_candidate.safety_ratings])

                 # Tenta obter feedback do prompt (mais comum para bloqueio de *prompt*)
                 elif response.prompt_feedback and response.prompt_feedback.block_reason:
                      block_reason = response.prompt_feedback.block_reason.name
                      block_reason_message = response.prompt_feedback.block_reason_message or block_reason_message
                      if response.prompt_feedback.safety_ratings:
                           ratings_message = ", ".join([f"{r.category.name}: {r.probability.name}" for r in response.prompt_feedback.safety_ratings])

                 logger.warning(f"Resposta da IA bloqueada (C/E). Razão: {block_reason}. Detalhes: '{block_reason_message}'. Ratings: [{ratings_message}]")
                 raise AIResponseError(f"A geração foi bloqueada pela API ({block_reason}). Ajuste as configurações de segurança ou o prompt.")

            elif not first_candidate or not hasattr(first_candidate.content, 'parts') or not first_candidate.content.parts:
                 # Caso estranho: Sem candidato, sem conteúdo ou sem 'parts'
                 finish_reason = first_candidate.finish_reason.name if first_candidate else "N/A"
                 logger.warning(f"Resposta da IA vazia ou inválida (C/E). Finish Reason: {finish_reason}. Resposta completa: {response}")
                 raise AIResponseError(f"A IA retornou uma resposta vazia ou inválida (Finish Reason: {finish_reason}).")
            # --- Fim Verificação de Bloqueio ---


            # Se não foi bloqueado, processa o texto da primeira parte do primeiro candidato
            generated_text = first_candidate.content.parts[0].text
            # Chama o método de parsing interno (que agora extrai afirmação e gabarito)
            parsed_questions = self._parse_questions(generated_text) # Chama o parser abaixo
            return parsed_questions

        except AIResponseError as e:
            # Relança o erro de bloqueio já tratado
            raise e
        except Exception as e:
            # Pega outros erros da API ou de comunicação
            logger.error(f"Erro na chamada da API Google AI (C/E): {e}", exc_info=True)
            # Simplifica a verificação de erro de segurança/bloqueio
            if "safety" in str(e).lower() or "blocked" in str(e).lower() or "API key" in str(e):
                 raise AIResponseError(f"Erro relacionado à API ou segurança (C/E): {e}")
            else: # Assume erro de comunicação/serviço genérico
                 raise AIServiceError(f"Erro na comunicação com a API Google AI (C/E): {e}")
    # --- FIM DO MÉTODO generate_questions ---


    # --- MÉTODO _parse_questions (sem alterações necessárias aqui) ---
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
                # Usando startswith para maior robustez
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
                    # Permite apenas C ou E
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
                    # Adiciona espaço antes para juntar palavras corretamente
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
            # É melhor lançar um erro específico de parsing para a view tratar
            raise ParsingError(f"Erro ao processar a estrutura da resposta da IA: {e}")
            # return structured_questions # Evitar retornar lista parcial em caso de erro grave

        logger.info(f"Resultado ESTRUTURADO FINAL (Afirmação/Gabarito) - {len(structured_questions)} itens")
        if not structured_questions and text:
             logger.warning(f"Não foi possível fazer o parsing C/E de nenhum item formatado do texto: '{text[:200]}...'")
             # Lança erro se o texto não era vazio mas nada foi parseado
             raise ParsingError("A resposta da IA não continha itens no formato esperado (Afirmação/Gabarito).")


        return structured_questions
    # --- FIM DO MÉTODO _parse_questions ---