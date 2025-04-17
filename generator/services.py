# generator/services.py (CORRIGIDO - MÉTODO FALTANDO ADICIONADO)

import logging
from django.conf import settings
import google.generativeai as genai
# Corrigido para importar HarmBlockThreshold corretamente
from google.generativeai.types import HarmCategory, HarmBlockThreshold, GenerationConfig # Importar GenerationConfig
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
            # <<< CORREÇÃO: Usar GenerationConfig diretamente >>>
            self.generation_config = GenerationConfig(
                temperature=getattr(settings, 'AI_GENERATION_TEMPERATURE', 0.7) # Exemplo de default
                # Adicione outros parâmetros de Geração aqui se necessário (ex: max_output_tokens)
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
             missing_setting = str(e).split("'")[-2]
             raise ConfigurationError(f"Configuração obrigatória ausente em settings.py: '{missing_setting}'")
        except ConfigurationError as e:
             raise e
        except Exception as e:
            logger.critical(f"Falha inesperada ao inicializar o cliente Google AI: {e}", exc_info=True)
            raise ConfigurationError(f"Falha inesperada ao inicializar o cliente Google AI: {e}")

    def _load_and_convert_safety_settings(self):
        """Carrega as configurações de segurança do settings.py e converte strings para enums."""
        raw_settings = getattr(settings, 'GOOGLE_AI_SAFETY_SETTINGS', None)
        if not raw_settings or not isinstance(raw_settings, list):
            logger.warning("GOOGLE_AI_SAFETY_SETTINGS não definidas, vazias ou inválidas em settings.py. Usando padrões da API.")
            self.safety_settings = None
            return

        converted_settings = []
        category_map = {name: member for name, member in HarmCategory.__members__.items()}
        threshold_map = {name: member for name, member in HarmBlockThreshold.__members__.items()}

        try:
            for setting in raw_settings:
                if not isinstance(setting, dict):
                    logger.warning(f"Item inválido em GOOGLE_AI_SAFETY_SETTINGS (não é dicionário): {setting}")
                    continue
                category_str = setting.get("category")
                threshold_str = setting.get("threshold")
                if category_str is None or threshold_str is None:
                    logger.warning(f"Dicionário incompleto em GOOGLE_AI_SAFETY_SETTINGS: {setting}")
                    continue
                category_enum = category_map.get(category_str)
                threshold_enum = threshold_map.get(threshold_str)
                if category_enum is None:
                     logger.error(f"Valor inválido para 'category' em GOOGLE_AI_SAFETY_SETTINGS: '{category_str}'. Pulando.")
                     continue
                if threshold_enum is None:
                     logger.error(f"Valor inválido para 'threshold' em GOOGLE_AI_SAFETY_SETTINGS: '{threshold_str}'. Pulando.")
                     continue
                converted_settings.append({"category": category_enum, "threshold": threshold_enum})

            if converted_settings:
                 self.safety_settings = converted_settings
                 logger.info(f"Configurações de segurança carregadas: {len(converted_settings)} regras.")
                 logger.debug(f"Detalhe Safety Settings: {self.safety_settings}")
            else:
                 logger.warning("Nenhuma configuração de segurança válida encontrada.")
                 self.safety_settings = None
        except Exception as e:
             logger.error(f"Erro ao processar GOOGLE_AI_SAFETY_SETTINGS: {e}", exc_info=True)
             raise ConfigurationError(f"Erro ao processar GOOGLE_AI_SAFETY_SETTINGS: {e}")

    # --- MÉTODO generate_questions (Mantido como antes) ---
    def generate_questions(self, topic, num_questions, difficulty_level='medio'):
        """Gera afirmações estilo C/E com gabarito usando a API do Google AI."""
        if not self.model:
            raise ConfigurationError("Serviço de IA não inicializado corretamente.")
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
        if self.safety_settings:
            logger.info(f"SERVICE CALL (C/E): Usando {len(self.safety_settings)} regras de segurança carregadas.")
            logger.debug(f"Detalhe Safety Settings para chamada: {self.safety_settings}")
        else:
            logger.info("SERVICE CALL (C/E): Usando configurações de segurança padrão da API.")
        try:
            logger.info(f"Enviando requisição (C/E) para API (Modelo: {self.model._model_name}, Tópico: {topic[:50]}..., Dificuldade: {difficulty_level})")
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )
            # Verificação de Bloqueio
            first_candidate = response.candidates[0] if response.candidates else None
            if first_candidate and first_candidate.finish_reason.name == 'SAFETY':
                 # ... (lógica de log e raise AIResponseError para bloqueio) ...
                 block_reason = "SAFETY"; block_reason_message = "Resposta bloqueada."; ratings_message = ""
                 if first_candidate.safety_ratings: ratings_message = ", ".join([f"{r.category.name}: {r.probability.name}" for r in first_candidate.safety_ratings])
                 elif response.prompt_feedback and response.prompt_feedback.block_reason: block_reason = response.prompt_feedback.block_reason.name; block_reason_message = response.prompt_feedback.block_reason_message or block_reason_message; # etc...
                 logger.warning(f"Resposta da IA bloqueada (C/E). Razão: {block_reason}. Detalhes: '{block_reason_message}'. Ratings: [{ratings_message}]")
                 raise AIResponseError(f"A geração foi bloqueada pela API ({block_reason}). Ajuste as configurações de segurança ou o prompt.")
            elif not first_candidate or not hasattr(first_candidate.content, 'parts') or not first_candidate.content.parts:
                 finish_reason = first_candidate.finish_reason.name if first_candidate else "N/A"
                 logger.warning(f"Resposta da IA vazia ou inválida (C/E). Finish Reason: {finish_reason}. Resposta completa: {response}")
                 raise AIResponseError(f"A IA retornou uma resposta vazia ou inválida (Finish Reason: {finish_reason}).")
            generated_text = first_candidate.content.parts[0].text
            parsed_questions = self._parse_questions(generated_text)
            return parsed_questions
        except AIResponseError as e:
            raise e
        except Exception as e:
            logger.error(f"Erro na chamada da API Google AI (C/E): {e}", exc_info=True)
            if "safety" in str(e).lower() or "blocked" in str(e).lower() or "API key" in str(e):
                 raise AIResponseError(f"Erro relacionado à API ou segurança (C/E): {e}")
            else:
                 raise AIServiceError(f"Erro na comunicação com a API Google AI (C/E): {e}")

    # --- MÉTODO _parse_questions (Mantido como antes) ---
    def _parse_questions(self, text: str) -> list:
        """Faz o parsing do texto bruto da IA para extrair C/E."""
        if not text: return []
        logger.debug(f"Texto recebido para parsing (C/E): >>>\n{text}\n<<<")
        structured_questions = []
        current_affirmation = None
        current_gabarito = None
        lines = text.strip().split('\n')
        try:
            for line_num, line in enumerate(lines):
                cleaned_line = line.strip()
                if not cleaned_line: continue
                if cleaned_line.upper().startswith("AFIRMAÇÃO:"):
                    if current_affirmation is not None and current_gabarito is not None:
                        structured_questions.append({'afirmacao': current_affirmation, 'gabarito': current_gabarito})
                    current_affirmation = cleaned_line[len("Afirmação:"):].strip()
                    current_gabarito = None
                elif cleaned_line.upper().startswith("GABARITO:") and current_affirmation is not None:
                    gabarito_text = cleaned_line[len("Gabarito:"):].strip().upper()
                    if gabarito_text in ['C', 'E']: current_gabarito = gabarito_text
                    else: logger.warning(f"Linha {line_num+1}: Gabarito inválido ('{gabarito_text}') encontrado."); current_affirmation = None; current_gabarito = None # Descarta item
                elif cleaned_line == "---":
                     if current_affirmation is not None and current_gabarito is not None:
                          structured_questions.append({'afirmacao': current_affirmation, 'gabarito': current_gabarito})
                     current_affirmation = None; current_gabarito = None
                elif current_affirmation is not None and current_gabarito is None:
                    current_affirmation += " " + cleaned_line # Continuação da afirmação
                elif cleaned_line:
                     logger.warning(f"Linha {line_num+1}: Texto inesperado ignorado: '{cleaned_line}'")
            if current_affirmation is not None and current_gabarito is not None: # Adiciona último item
                structured_questions.append({'afirmacao': current_affirmation, 'gabarito': current_gabarito})
        except Exception as e:
            logger.error(f"Erro durante o parsing C/E: {e}", exc_info=True)
            raise ParsingError(f"Erro ao processar a estrutura da resposta C/E da IA: {e}")
        logger.info(f"Resultado ESTRUTURADO FINAL (Afirmação/Gabarito) - {len(structured_questions)} itens")
        if not structured_questions and text:
             logger.warning(f"Não foi possível fazer o parsing C/E de nenhum item do texto: '{text[:200]}...'")
             raise ParsingError("A resposta da IA não continha itens no formato esperado (Afirmação/Gabarito).")
        return structured_questions

    # --- <<< NOVO MÉTODO ADICIONADO >>> ---
    def generate_discursive_exam_question(self, base_topic_or_context, num_aspects=3, area=None, complexity='Intermediária', language='pt-br'):
        """
        Gera uma questão discursiva estruturada (comando, aspectos) com base em um tópico/contexto.
        """
        if not self.model:
            raise ConfigurationError("Serviço de IA não inicializado corretamente.")

        # Construção do Prompt Detalhado
        prompt_parts = [
            f"**Instrução Principal:** Elabore uma questão de prova discursiva completa, no idioma '{language}', baseada no seguinte tópico geral ou texto de contexto:",
            f"'{base_topic_or_context}'\n",
            f"**Estrutura OBRIGATÓRIA da Saída:** A questão deve ser estruturada contendo:",
            "1.  **Texto(s) Motivador(es):** Um ou mais textos curtos introdutórios relevantes (se aplicável, derivados do contexto fornecido ou criados com base no tópico). Pode ser omitido se o contexto fornecido for suficiente.",
            "2.  **Comando:** A pergunta principal clara e direta que o candidato deve responder.",
            f"3.  **Aspectos:** Exatamente {num_aspects} aspectos ou sub-itens específicos que a resposta deve abordar, listados de forma clara (ex: a), b), c)).\n",
            f"**Diretrizes Adicionais:**",
            f"- A complexidade da questão e dos aspectos deve ser '{complexity}'.",
        ]
        if area:
            prompt_parts.append(f"- A questão deve ser relevante para a área de conhecimento: '{area}'. Use vocabulário apropriado.")
        prompt_parts.append("- O comando e os aspectos devem ser diretamente relacionados ao tópico/contexto fornecido.")
        prompt_parts.append("- Certifique-se de que a resposta à questão exige análise e desenvolvimento, não apenas cópia.")
        prompt_parts.append("\n**Formato da Saída:** Apresente a questão completa em texto corrido ou markdown leve, seguindo a estrutura (Textos Motivadores, Comando, Aspectos).")

        prompt = "\n".join(prompt_parts)

        if self.safety_settings:
            logger.info(f"SERVICE CALL (Disc. Q): Usando {len(self.safety_settings)} regras de segurança carregadas.")
            logger.debug(f"Detalhe Safety Settings para chamada: {self.safety_settings}")
        else:
            logger.info("SERVICE CALL (Disc. Q): Usando configurações de segurança padrão da API.")

        try:
            logger.info(f"Enviando requisição (Disc. Q) para API (Modelo: {self.model._model_name}, Tópico: {base_topic_or_context[:50]}..., Complexidade: {complexity})")

            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )

            # Verificação de Bloqueio (similar ao outro método)
            first_candidate = response.candidates[0] if response.candidates else None
            if first_candidate and first_candidate.finish_reason.name == 'SAFETY':
                 # ... (lógica de log e raise AIResponseError para bloqueio) ...
                 block_reason = "SAFETY"; block_reason_message = "Resposta bloqueada."; ratings_message = ""
                 if first_candidate.safety_ratings: ratings_message = ", ".join([f"{r.category.name}: {r.probability.name}" for r in first_candidate.safety_ratings])
                 elif response.prompt_feedback and response.prompt_feedback.block_reason: block_reason = response.prompt_feedback.block_reason.name; block_reason_message = response.prompt_feedback.block_reason_message or block_reason_message; # etc...
                 logger.warning(f"Resposta da IA bloqueada (Disc. Q). Razão: {block_reason}. Detalhes: '{block_reason_message}'. Ratings: [{ratings_message}]")
                 raise AIResponseError(f"A geração da questão discursiva foi bloqueada pela API ({block_reason}). Ajuste as configurações de segurança ou o prompt.")
            elif not first_candidate or not hasattr(first_candidate.content, 'parts') or not first_candidate.content.parts:
                 finish_reason = first_candidate.finish_reason.name if first_candidate else "N/A"
                 logger.warning(f"Resposta da IA vazia ou inválida (Disc. Q). Finish Reason: {finish_reason}. Resposta completa: {response}")
                 raise AIResponseError(f"A IA retornou uma resposta vazia ou inválida ao gerar a questão discursiva (Finish Reason: {finish_reason}).")

            # Se passou, retorna o texto gerado
            generated_text = first_candidate.content.parts[0].text
            logger.info("Texto da questão discursiva gerado com sucesso pela IA.")
            logger.debug(f"Texto Gerado (Disc. Q): {generated_text[:200]}...") # Log do início do texto
            return generated_text

        except AIResponseError as e:
            # Relança o erro de bloqueio já tratado
            raise e
        except Exception as e:
            # Pega outros erros da API ou de comunicação
            logger.error(f"Erro na chamada da API Google AI (Disc. Q): {e}", exc_info=True)
            if "safety" in str(e).lower() or "blocked" in str(e).lower() or "API key" in str(e):
                 raise AIResponseError(f"Erro relacionado à API ou segurança (Disc. Q): {e}")
            else: # Assume erro de comunicação/serviço genérico
                 raise AIServiceError(f"Erro na comunicação com a API Google AI (Disc. Q): {e}")
    # --- <<< FIM DO NOVO MÉTODO >>> ---


    # --- MÉTODO generate_discursive_answer (Adicione se necessário, exemplo abaixo) ---
    def generate_discursive_answer(self, essay_prompt, key_points=None, limit=None, area=None):
        """
        Gera uma resposta discursiva modelo para um dado comando/prompt.
        (Este método já existia na sua view, então o adiciono aqui para completar o serviço)
        """
        if not self.model:
            raise ConfigurationError("Serviço de IA não inicializado corretamente.")

        prompt_parts = [
            f"**Instrução Principal:** Elabore uma resposta discursiva completa e bem fundamentada para o seguinte comando:",
            f"'{essay_prompt}'\n"
        ]
        if key_points:
            prompt_parts.append(f"**Pontos-Chave Obrigatórios:** A resposta DEVE abordar os seguintes pontos:\n{key_points}\n")
        if limit:
             prompt_parts.append(f"**Limite de Tamanho:** A resposta deve respeitar o limite aproximado de '{limit}'.")
        if area:
             prompt_parts.append(f"**Área de Conhecimento:** Contextualize a resposta na área de '{area}'.")

        prompt_parts.append("\n**Diretrizes Adicionais:**")
        prompt_parts.append("- Use linguagem formal e clara.")
        prompt_parts.append("- Apresente argumentos coesos e coerentes.")
        prompt_parts.append("- Se possível, cite fontes ou conceitos relevantes (de forma genérica, se não houver dados específicos).")

        prompt = "\n".join(prompt_parts)

        # ... (Lógica de chamada à API e tratamento de erro similar aos outros métodos) ...
        if self.safety_settings: logger.info(f"SERVICE CALL (Disc. Ans): Usando {len(self.safety_settings)} regras de segurança.")
        else: logger.info("SERVICE CALL (Disc. Ans): Usando safety settings padrão.")
        try:
            logger.info(f"Enviando requisição (Disc. Ans) para API (Modelo: {self.model._model_name}, Prompt: {essay_prompt[:50]}...)")
            response = self.model.generate_content(prompt, generation_config=self.generation_config, safety_settings=self.safety_settings)

            # Verificação de Bloqueio
            first_candidate = response.candidates[0] if response.candidates else None
            if first_candidate and first_candidate.finish_reason.name == 'SAFETY':
                 block_reason = "SAFETY"; block_reason_message = "Resposta bloqueada."; ratings_message = "" # ... (Lógica de log detalhado do bloqueio) ...
                 logger.warning(f"Resposta da IA bloqueada (Disc. Ans). Razão: {block_reason}.")
                 raise AIResponseError(f"A geração da resposta foi bloqueada pela API ({block_reason}).")
            elif not first_candidate or not hasattr(first_candidate.content, 'parts') or not first_candidate.content.parts:
                 finish_reason = first_candidate.finish_reason.name if first_candidate else "N/A"
                 logger.warning(f"Resposta da IA vazia ou inválida (Disc. Ans). Finish Reason: {finish_reason}.")
                 raise AIResponseError(f"A IA retornou uma resposta vazia ou inválida (Finish Reason: {finish_reason}).")

            generated_text = first_candidate.content.parts[0].text
            logger.info("Texto da resposta discursiva gerado com sucesso pela IA.")
            return generated_text
        except AIResponseError as e:
             raise e
        except Exception as e:
             logger.error(f"Erro na chamada da API Google AI (Disc. Ans): {e}", exc_info=True)
             if "safety" in str(e).lower() or "blocked" in str(e).lower() or "API key" in str(e):
                 raise AIResponseError(f"Erro API/segurança (Disc. Ans): {e}")
             else:
                 raise AIServiceError(f"Erro comunicação API (Disc. Ans): {e}")

    # --- MÉTODO evaluate_discursive_answer (Adicione se necessário, exemplo abaixo) ---
    def evaluate_discursive_answer(self, exam_context, user_answer, line_count=None):
        """
        Avalia uma resposta discursiva fornecida pelo usuário em relação a um contexto/comando.
        (Este método já existia na sua view, então o adiciono aqui para completar o serviço)
        """
        if not self.model:
            raise ConfigurationError("Serviço de IA não inicializado corretamente.")

        # Prompt para avaliação (EXEMPLO - AJUSTE CONFORME NECESSÁRIO)
        prompt_parts = [
            "**Instrução Principal:** Avalie a 'Resposta do Usuário' fornecida abaixo, considerando o 'Comando da Questão'.",
            "Forneça uma análise detalhada incluindo:",
            "1.  **Nota de Conteúdo (NC):** Uma nota de 0 a X (defina seu X, ex: 30.00) avaliando o atendimento aos aspectos implícitos ou explícitos no comando. Justifique brevemente.",
            "2.  **Contagem de Erros (NE):** Uma contagem estimada de erros gramaticais ou de norma culta.",
            "3.  **Nota Final (NPD):** Calcule a nota final (se houver uma fórmula padrão, como NC - k*NE).",
            "4.  **Comentários/Feedback:** Um feedback geral sobre a qualidade da resposta.\n",
            "---",
            "**Comando da Questão:**",
            f"{exam_context}",
            "---",
            "**Resposta do Usuário:**"
        ]
        if line_count and line_count != '0':
             prompt_parts.append(f"(Resposta com aproximadamente {line_count} linhas)")
        prompt_parts.append(f"{user_answer}")
        prompt_parts.append("---")
        prompt_parts.append("**Formato da Saída:** Apresente a avaliação de forma clara, usando marcadores como 'NC:', 'NE:', 'NPD:', 'Comentários:'.")

        prompt = "\n".join(prompt_parts)

        # ... (Lógica de chamada à API e tratamento de erro similar aos outros métodos) ...
        if self.safety_settings: logger.info(f"SERVICE CALL (Disc. Eval): Usando {len(self.safety_settings)} regras de segurança.")
        else: logger.info("SERVICE CALL (Disc. Eval): Usando safety settings padrão.")
        try:
             logger.info(f"Enviando requisição (Disc. Eval) para API (Modelo: {self.model._model_name}, Contexto: {exam_context[:50]}...)")
             response = self.model.generate_content(prompt, generation_config=self.generation_config, safety_settings=self.safety_settings)

             # Verificação de Bloqueio
             first_candidate = response.candidates[0] if response.candidates else None
             if first_candidate and first_candidate.finish_reason.name == 'SAFETY':
                  block_reason = "SAFETY"; block_reason_message = "Resposta bloqueada."; ratings_message = "" # ... (Lógica de log detalhado do bloqueio) ...
                  logger.warning(f"Resposta da IA bloqueada (Disc. Eval). Razão: {block_reason}.")
                  raise AIResponseError(f"A avaliação foi bloqueada pela API ({block_reason}).")
             elif not first_candidate or not hasattr(first_candidate.content, 'parts') or not first_candidate.content.parts:
                  finish_reason = first_candidate.finish_reason.name if first_candidate else "N/A"
                  logger.warning(f"Resposta da IA vazia ou inválida (Disc. Eval). Finish Reason: {finish_reason}.")
                  raise AIResponseError(f"A IA retornou uma resposta vazia ou inválida (Finish Reason: {finish_reason}).")

             generated_text = first_candidate.content.parts[0].text
             logger.info("Texto da avaliação discursiva recebido da IA.")
             # A view será responsável por chamar o parser para este texto
             return generated_text
        except AIResponseError as e:
              raise e
        except Exception as e:
              logger.error(f"Erro na chamada da API Google AI (Disc. Eval): {e}", exc_info=True)
              if "safety" in str(e).lower() or "blocked" in str(e).lower() or "API key" in str(e):
                  raise AIResponseError(f"Erro API/segurança (Disc. Eval): {e}")
              else:
                  raise AIServiceError(f"Erro comunicação API (Disc. Eval): {e}")