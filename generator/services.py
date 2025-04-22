# generator/services.py (VERSÃO REESCRITA E CORRIGIDA)

import logging
from django.conf import settings
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold, GenerationConfig
# <<< Importa os PARSERS e EXCEÇÕES locais >>>
from .utils import parse_ai_response_to_questions, parse_evaluation_scores # Garanta que este utils.py exista e contenha as funções
from .exceptions import ConfigurationError, AIServiceError, AIResponseError, ParsingError # Garanta que este exceptions.py exista

# Define o logger UMA VEZ
logger = logging.getLogger('generator')

# --- CLASSE QuestionGenerationService (DEFINIÇÃO ÚNICA E CORRIGIDA) ---
class QuestionGenerationService:
    def __init__(self):
        """Inicializa o serviço, configurando a API e o modelo."""
        self.model = None
        self.generation_config = None
        self.safety_settings = None
        try:
            # 1. Valida e configura a API Key
            api_key = settings.GOOGLE_API_KEY
            if not api_key:
                # Levanta erro específico se a chave não estiver definida
                raise ConfigurationError("Configuração Ausente: GOOGLE_API_KEY não definida nas configurações do Django.")
            genai.configure(api_key=api_key)

            # 2. Configura Geração (Temperatura)
            # Usa 0.7 como padrão se não definido nas settings
            temperature = getattr(settings, 'AI_GENERATION_TEMPERATURE', 0.7)
            self.generation_config = GenerationConfig(temperature=temperature)

            # 3. Valida e configura o Nome do Modelo
            model_name = getattr(settings, 'AI_MODEL_NAME', None)
            if not model_name:
                # Levanta erro específico se o nome não estiver definido
                raise ConfigurationError("Configuração Ausente: AI_MODEL_NAME não definido nas configurações do Django.")
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"Modelo Generative AI '{model_name}' inicializado com sucesso (Temperatura: {temperature}).")

            # 4. Carrega Configurações de Segurança
            self._load_and_convert_safety_settings()

        except ConfigurationError as e:
            # Repassa erros de configuração específicos
            logger.error(f"Erro de Configuração no Serviço IA: {e}")
            raise e
        except Exception as e:
            # Captura qualquer outro erro durante a inicialização
            logger.critical(f"Falha crítica na inicialização do Serviço Google AI: {e}", exc_info=True)
            # Encapsula como ConfigurationError para indicar falha na configuração/inicialização
            raise ConfigurationError(f"Falha na inicialização do Serviço Google AI: {e}")

    def _load_and_convert_safety_settings(self):
        """Carrega e converte as configurações de segurança do Django settings."""
        # Lógica completa restaurada da primeira definição original
        raw_settings = getattr(settings, 'GOOGLE_AI_SAFETY_SETTINGS', None)
        if not raw_settings or not isinstance(raw_settings, list):
            logger.warning("GOOGLE_AI_SAFETY_SETTINGS não definidas ou inválidas no settings.py. Usando padrões da API.")
            self.safety_settings = None
            return

        converted_settings = []
        # Mapeia strings para Enums da biblioteca genai
        category_map = {name: member for name, member in HarmCategory.__members__.items()}
        threshold_map = {name: member for name, member in HarmBlockThreshold.__members__.items()}

        try:
            for setting in raw_settings:
                if not isinstance(setting, dict):
                    logger.warning(f"Item inválido encontrado em GOOGLE_AI_SAFETY_SETTINGS (esperado dict): {setting}")
                    continue
                category_str = setting.get("category")
                threshold_str = setting.get("threshold")

                if category_str is None or threshold_str is None:
                    logger.warning(f"Dicionário incompleto em GOOGLE_AI_SAFETY_SETTINGS (faltando 'category' ou 'threshold'): {setting}")
                    continue

                category_enum = category_map.get(category_str)
                threshold_enum = threshold_map.get(threshold_str)

                if category_enum is None:
                    logger.error(f"Valor de 'category' inválido em GOOGLE_AI_SAFETY_SETTINGS: '{category_str}'. Valores válidos: {list(category_map.keys())}")
                    continue # Pula esta configuração inválida
                if threshold_enum is None:
                    logger.error(f"Valor de 'threshold' inválido em GOOGLE_AI_SAFETY_SETTINGS: '{threshold_str}'. Valores válidos: {list(threshold_map.keys())}")
                    continue # Pula esta configuração inválida

                converted_settings.append({"category": category_enum, "threshold": threshold_enum})

            if converted_settings:
                self.safety_settings = converted_settings
                logger.info(f"Configurações de Segurança da IA carregadas e convertidas com sucesso ({len(converted_settings)} regras).")
                logger.debug(f"Safety Settings Ativas: {self.safety_settings}")
            else:
                logger.warning("Nenhuma configuração de segurança válida foi encontrada após processamento. Usando padrões da API.")
                self.safety_settings = None
        except Exception as e:
            logger.error(f"Erro inesperado ao processar GOOGLE_AI_SAFETY_SETTINGS: {e}", exc_info=True)
            # Levanta ConfigurationError pois afeta a configuração do serviço
            raise ConfigurationError(f"Erro ao processar as Configurações de Segurança da IA: {e}")

    # --- MÉTODO generate_questions (COM PROMPT CORRIGIDO) ---
    def generate_questions(self, topic, num_questions, difficulty_level='medio'):
        """Gera 1 Texto Motivador + N Itens C/E estilo Cebraspe/CESPE."""
        if not self.model:
            raise ConfigurationError("Serviço de IA não inicializado corretamente.")

        # <<< PROMPT CORRIGIDO (Guideline 1 alinhada com Formato de Saída) >>>
        prompt = (
            f"**Persona:** Você é um examinador experiente da banca Cebraspe/CESPE, conhecido pelo rigor técnico.\n"
            f"**Tarefa:** Gerar {num_questions} itens inéditos (Certo/Errado) sobre o tópico/contexto: '{topic}', com nível de dificuldade '{difficulty_level}'.\n"
            f"**Estilo Cebraspe OBRIGATÓRIO:**\n"
            # CORRIGIDO: Alinhado com o formato de saída.
            f"1.  **Estrutura Completa:** Texto Motivador, Comando claro, Item analítico.\n"
            f"2.  **Item Analítico e Nuance:** O Item (afirmação) NÃO PODE ser óbvio. Deve exigir análise crítica, interpretação, conhecimento de exceções, condições, jurisprudência ou detalhes específicos.\n"
            f"3.  **EVITAR ABSOLUTOS:** RESTRINJA AO MÁXIMO o uso de termos absolutos (sempre, nunca...). Prefira condições, exceções, probabilidades (uso aceitável de absoluto apenas se for o cerne técnico).\n"
            f"4.  **Mistura de Conceitos (Pegadinha Comum):** Se o tópico '{topic}' contiver conceitos similares mas distintos (ex: Data Lake vs Data Warehouse; Princípio X vs Princípio Y; Etapa A vs Etapa B de um processo), elabore itens que **intencionalmente misturem ou troquem características, definições ou aplicações entre eles** para gerar afirmações **ERRADAS** que testem o conhecimento preciso das diferenças. Deixe claro na justificativa qual foi a mistura feita.\n"
            f"5.  **Indução ao Erro (com Fundamento):** Formule itens que possam levar um candidato com leitura apressada ou conhecimento incompleto ao erro, mas que possuam um gabarito e justificativa tecnicamente impecáveis.\n"
            f"6.  **Gabarito Inequívoco:** Item DEVE ter gabarito CLARO (C ou E).\n"
            f"7.  **Justificativa Detalhada:** Explicar o raciocínio técnico, desmontando a 'pegadinha' e justificando a resposta correta.\n\n"
            f"**Formato ESTRITO de Saída:**\n"
            f"Use EXATAMENTE os marcadores em negrito abaixo para CADA UM dos {num_questions} itens. Separe itens completos APENAS com '---'.\n\n"
            f"**Texto Motivador:** [Texto curto OU 'Não aplicável'.]\n"
            f"**Comando:** [Instrução para julgar. Ex: 'Considerando X, julgue o item.']\n"
            f"**Item:** [A afirmação C/E analítica/desafiadora.]\n"
            f"**Gabarito:** [C ou E]\n"
            f"**Justificativa:** [Explicação técnica detalhada, incluindo a explicação da mistura de conceitos se usada.]\n"
            f"---\n"
            f"(Repita {num_questions} vezes)"
        )
        # <<< FIM DO PROMPT >>>

        if self.safety_settings:
            logger.info(f"SERVICE CALL (C/E Estruturado): Usando {len(self.safety_settings)} regras de segurança.")
        else:
            logger.info("SERVICE CALL (C/E Estruturado): Usando safety padrão.")

        try:
            # Usa _model_name se existir, senão informa N/A
            model_name_info = self.model._model_name if hasattr(self.model, '_model_name') else 'N/A'
            logger.info(f"Enviando req (C/E Estruturado) API (Modelo: {model_name_info}, Tópico: {topic[:50]}...)")

            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )

            first_candidate = response.candidates[0] if response.candidates else None

            # Validação da Resposta da API
            if first_candidate and hasattr(first_candidate, 'finish_reason') and first_candidate.finish_reason.name == 'SAFETY':
                logger.warning(f"Resposta IA bloqueada por SAFETY (C/E Estruturado).")
                raise AIResponseError(f"Geração de questões bloqueada pela API (SAFETY).")

            if not first_candidate or not hasattr(first_candidate, 'content') or not hasattr(first_candidate.content, 'parts') or not first_candidate.content.parts:
                finish_reason = "N/A"
                if first_candidate and hasattr(first_candidate, 'finish_reason'):
                    finish_reason = first_candidate.finish_reason.name
                logger.warning(f"Resposta IA vazia/inválida (C/E Estruturado). Finish Reason: {finish_reason}.")
                raise AIResponseError(f"IA retornou resposta vazia ou inválida (Finish Reason: {finish_reason}).")

            generated_text = first_candidate.content.parts[0].text
            logger.info("Texto C/E Estruturado recebido da IA. Chamando parser...")

            # Chama o método interno que delega para utils.py
            parsed_data = self._parse_questions(generated_text)
            return parsed_data # Retorna a tupla (motivador, lista_questoes)

        except AIResponseError as e: # Repassa erros específicos da IA
            raise e
        except ParsingError as e: # Repassa erros específicos do parsing
            logger.error(f"Erro durante o PARSING da resposta da IA (C/E Estruturado): {e}", exc_info=True)
            # Mantém o tipo ParsingError para tratamento específico se necessário
            raise ParsingError(f"Erro ao processar a estrutura da resposta da IA (C/E): {e}")
        except Exception as e: # Captura outros erros (rede, API genérica, etc.)
            logger.error(f"Erro GERAL durante chamada à API (C/E Estruturado): {e}", exc_info=True)
            raise AIServiceError(f"Erro na comunicação com a API (C/E): {e}")

    # --- Método _parse_questions (Chama utils.py) ---
    def _parse_questions(self, text: str):
        """Delega o parsing C/E para a função especializada em utils.py."""
        logger.debug("Service: _parse_questions iniciando chamada a utils.parse_ai_response_to_questions")
        try:
            # Chama a função importada de utils.py
            # Espera-se que ela retorne a tupla (motivador, lista_questoes) ou levante ParsingError
            parsed_result = parse_ai_response_to_questions(text)
            logger.debug("Service: _parse_questions retornou de utils.parse_ai_response_to_questions com sucesso.")
            return parsed_result
        except ParsingError as e:
            # Loga o erro específico de parsing e o repassa
            logger.error(f"Erro retornado pelo parser C/E (utils.parse_ai_response_to_questions): {e}")
            raise e # Repassa a exceção ParsingError
        except Exception as e:
            # Captura qualquer outro erro inesperado durante a chamada do parser
            logger.error(f"Erro inesperado ao chamar o parser C/E (utils.parse_ai_response_to_questions): {e}", exc_info=True)
            # Encapsula como ParsingError para sinalizar que o problema ocorreu nesta fase
            raise ParsingError(f"Erro inesperado durante o processamento da resposta C/E: {e}")

    # --- MÉTODO generate_discursive_exam_question (Mantido como estava) ---
    def generate_discursive_exam_question(self, base_topic_or_context, num_aspects=3, area=None, complexity='Intermediária', language='pt-br'):
        """Gera uma questão discursiva completa (Motivador, Comando, Aspectos)."""
        if not self.model:
            raise ConfigurationError("Serviço de IA não inicializado corretamente.")

        prompt_parts = [
            f"**Instrução Principal:** Elabore uma questão discursiva completa e original em {language} sobre o tema ou contexto base:",
            f"'{base_topic_or_context}'\n",
            f"**Estrutura da Questão:**",
            "1. Texto(s) Motivador(es): (Opcional, use se agregar valor significativo ao contexto).",
            "2. Comando da Questão: (Claro, objetivo, instruindo o que o candidato deve fazer).",
            f"3. Tópicos/Aspectos para Abordagem OBRIGATÓRIA: (Exatamente {num_aspects} aspectos distintos, claros e relacionados ao comando).\n",
            f"**Diretrizes para Elaboração:**",
            f"- Nível de Complexidade Desejado: '{complexity}'.",
            (f"- Considerar a Área de Conhecimento: '{area}'." if area else ""),
            "- Foco em exigir análise, aplicação de conceitos ou argumentação, não apenas memorização.",
            "- Garantir que os aspectos sejam respondíveis com base no comando e no conhecimento esperado para a área/complexidade.",
            "\n**Formato de Saída:** Apresente a questão completa em texto corrido ou formato markdown, claramente separando Texto Motivador (se houver), Comando e Aspectos."
        ]
        prompt = "\n".join(filter(None, prompt_parts))

        if self.safety_settings:
            logger.info(f"SERVICE CALL (Disc. Q Gen): Usando {len(self.safety_settings)} regras de segurança.")
        else:
            logger.info("SERVICE CALL (Disc. Q Gen): Usando safety padrão.")

        try:
            model_name_info = self.model._model_name if hasattr(self.model, '_model_name') else 'N/A'
            logger.info(f"Enviando req (Disc. Q Gen) API (Modelo: {model_name_info})")

            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )

            first_candidate = response.candidates[0] if response.candidates else None

            if first_candidate and hasattr(first_candidate, 'finish_reason') and first_candidate.finish_reason.name == 'SAFETY':
                block_reason = "SAFETY"
                logger.warning(f"Resposta IA bloqueada por SAFETY (Disc. Q Gen). Razão: {block_reason}.")
                raise AIResponseError(f"Geração da questão discursiva bloqueada pela API ({block_reason}).")

            if not first_candidate or not hasattr(first_candidate, 'content') or not hasattr(first_candidate.content, 'parts') or not first_candidate.content.parts:
                finish_reason = "N/A"
                if first_candidate and hasattr(first_candidate, 'finish_reason'):
                    finish_reason = first_candidate.finish_reason.name
                logger.warning(f"Resposta IA vazia/inválida (Disc. Q Gen). Finish Reason: {finish_reason}.")
                raise AIResponseError(f"IA retornou resposta vazia ou inválida ao gerar questão discursiva (Finish Reason: {finish_reason}).")

            generated_text = first_candidate.content.parts[0].text
            logger.info("Texto da questão discursiva gerado pela IA.")
            return generated_text

        except AIResponseError as e:
            raise e
        except Exception as e:
            logger.error(f"Erro GERAL durante chamada à API (Disc. Q Gen): {e}", exc_info=True)
            raise AIServiceError(f"Erro na comunicação com a API ao gerar questão discursiva: {e}")

    # --- MÉTODO generate_discursive_answer (Mantido como estava) ---
    def generate_discursive_answer(self, essay_prompt, key_points=None, limit=None, area=None):
        """Gera uma resposta discursiva para um dado prompt."""
        if not self.model:
            raise ConfigurationError("Serviço de IA não inicializado corretamente.")

        prompt_parts = [
            f"**Instrução Principal:** Elabore uma resposta discursiva coesa, coerente e bem fundamentada para o seguinte comando/questão:",
            f"'{essay_prompt}'\n",
            (f"**Pontos-Chave a serem considerados/abordados (se fornecidos):**\n{key_points}\n" if key_points else ""),
            (f"**Limite de tamanho/formato (se especificado):** '{limit}'.\n" if limit else ""),
            (f"**Área de Conhecimento (para contexto):** '{area}'.\n" if area else ""),
            "\n**Diretrizes para a Resposta:**",
            "- Use linguagem formal e norma culta.",
            "- Estruture a resposta com introdução, desenvolvimento e conclusão.",
            "- Garanta coesão e coerência entre os parágrafos.",
            "- Se aplicável, cite fontes de forma genérica (ex: 'segundo a doutrina majoritária', 'conforme a legislação vigente') ou use conhecimentos gerais consolidados.",
            "- Respeite o limite de tamanho, se especificado."
        ]
        prompt = "\n".join(filter(None, prompt_parts))

        if self.safety_settings:
             logger.info(f"SERVICE CALL (Disc. Ans Gen): Usando {len(self.safety_settings)} regras de segurança.")
        else:
             logger.info("SERVICE CALL (Disc. Ans Gen): Usando safety padrão.")

        try:
            model_name_info = self.model._model_name if hasattr(self.model, '_model_name') else 'N/A'
            logger.info(f"Enviando req (Disc. Ans Gen) API (Modelo: {model_name_info})")

            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )

            first_candidate = response.candidates[0] if response.candidates else None

            if first_candidate and hasattr(first_candidate, 'finish_reason') and first_candidate.finish_reason.name == 'SAFETY':
                block_reason = "SAFETY"
                logger.warning(f"Resposta IA bloqueada por SAFETY (Disc. Ans Gen). Razão: {block_reason}.")
                raise AIResponseError(f"Geração da resposta discursiva bloqueada pela API ({block_reason}).")

            if not first_candidate or not hasattr(first_candidate, 'content') or not hasattr(first_candidate.content, 'parts') or not first_candidate.content.parts:
                finish_reason = "N/A"
                if first_candidate and hasattr(first_candidate, 'finish_reason'):
                    finish_reason = first_candidate.finish_reason.name
                logger.warning(f"Resposta IA vazia/inválida (Disc. Ans Gen). Finish Reason: {finish_reason}.")
                raise AIResponseError(f"IA retornou resposta vazia ou inválida ao gerar resposta discursiva (Finish Reason: {finish_reason}).")

            generated_text = first_candidate.content.parts[0].text
            logger.info("Texto da resposta discursiva gerado pela IA.")
            return generated_text

        except AIResponseError as e:
            raise e
        except Exception as e:
            logger.error(f"Erro GERAL durante chamada à API (Disc. Ans Gen): {e}", exc_info=True)
            raise AIServiceError(f"Erro na comunicação com a API ao gerar resposta discursiva: {e}")

    # --- MÉTODO evaluate_discursive_answer (Mantido como estava, com prompt RÍGIDO) ---
    def evaluate_discursive_answer(self, exam_context, user_answer, line_count=None):
        """Avalia resposta discursiva com regras RÍGIDAS (retorna texto bruto para parser externo)."""
        if not self.model:
            raise ConfigurationError("Serviço de IA não inicializado corretamente.")

        char_count = len(user_answer)
        # TODO: Considerar tornar min_chars e Max NC configuráveis via settings.py
        min_chars = 1400
        max_nc_value = 30.00

        prompt_parts = [
            "**Instrução Principal:** Avalie a 'Resposta do Usuário' de forma RÍGIDA E DETALHADA vs 'Comando da Questão'. Siga TODAS as regras:",
            "\n**Regra 1: Mínimo Caracteres:**",
            f"- Chars: {char_count}. Se < {min_chars}, é insuficiente. Indique CLARAMENTE 'Caracteres Insuficientes' nos Comentários e NPD = 0.00 (Eliminado). Ignore demais regras de nota (NC e NE), mas FORNEÇA feedback qualitativo sobre o conteúdo existente.",
            "\n**Regra 2: Avaliação por Aspectos (Aplicável SOMENTE SE Regra 1 OK):**",
            "- Identifique CLARAMENTE os aspectos (a, b, c...) solicitados no 'Comando da Questão'.",
            "- Avalie CADA aspecto presente na 'Resposta do Usuário'.",
            "- Se um aspecto do Comando NÃO foi respondido OU a resposta sobre ele é totalmente irrelevante/incorreta, a pontuação para ESSE aspecto é ZERO.",
            "\n**Regra 3: Nota Conteúdo (NC) Proporcional (Aplicável SOMENTE SE Regra 1 OK):**",
            f"- A Nota Máxima de Conteúdo (Max NC) possível é {max_nc_value}, distribuída igualmente entre os aspectos identificados no Comando.",
            "- Calcule a NC final proporcionalmente aos aspectos que foram BEM respondidos (com profundidade e correção adequadas). Exemplo: Se são 3 aspectos (valendo {max_nc_value/3:.2f} cada) e 2 foram BEM respondidos, a NC máxima alcançável seria {max_nc_value*2/3:.2f}. A NC final será um valor ATÉ esse máximo, dependendo da qualidade.",
            "- Na 'Justificativa NC', explique DETALHADAMENTE o cálculo: liste os aspectos do comando, indique quais foram respondidos (OK/Parcial/Não OK), como a proporcionalidade foi aplicada e justifique a nota final atribuída.",
            "\n**Regra 4: Nota Erros (NE) (Aplicável SOMENTE SE Regra 1 OK):**",
            "- Conte o número total de erros gramaticais e de norma culta (ortografia, concordância, regência, etc.) na 'Resposta do Usuário'.",
            "- O valor de NE é simplesmente essa contagem (um número inteiro).",
            "\n**Regra 5: Nota Final (NPD):**",
            f"- Se a Regra 1 falhou (Caracteres < {min_chars}), então NPD = 0.00.",
            f"- Se a Regra 1 foi OK, use a fórmula: NPD = NC - (2 * NE). O resultado não pode ser negativo (NPD mínimo é 0.00).",
            "\n**Regra 6: Feedback Geral (Comentários):**",
            "- Elabore um feedback geral sobre a resposta: qualidade da argumentação, clareza, coesão textual, atendimento geral ao comando.",
            "- Se a Regra 1 falhou, INCLUA a indicação 'Caracteres Insuficientes' neste campo.",
            "\n---",
            f"**Comando da Questão:**\n{exam_context}",
            "---",
            f"**Resposta do Usuário (Caracteres: {char_count}, Linhas: {line_count or 'N/A'}):**\n{user_answer}",
            "---",
            "**Formato OBRIGATÓRIO de Saída (Use EXATAMENTE estes marcadores em linhas separadas):**",
            "NC: [Valor float da NC calculada conforme Regra 3 OU 0.00 se Regra 1 falhou]",
            "NE: [Valor int de erros contados conforme Regra 4 OU 0 se Regra 1 falhou]",
            "NPD: [Valor float da NPD calculada conforme Regra 5]",
            "Justificativa NC: [Texto detalhado explicando o cálculo da NC conforme Regra 3]",
            "Comentários: [Feedback geral conforme Regra 6, incluindo 'Caracteres Insuficientes' se aplicável]"
        ]
        prompt = "\n".join(prompt_parts)

        if self.safety_settings:
            logger.info(f"SERVICE CALL (Disc. Eval Rigor): Usando {len(self.safety_settings)} regras de segurança.")
        else:
            logger.info("SERVICE CALL (Disc. Eval Rigor): Usando safety padrão.")

        try:
            model_name_info = self.model._model_name if hasattr(self.model, '_model_name') else 'N/A'
            logger.info(f"Enviando req (Disc. Eval Rigor) API (Modelo: {model_name_info})")

            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )

            first_candidate = response.candidates[0] if response.candidates else None

            if first_candidate and hasattr(first_candidate, 'finish_reason') and first_candidate.finish_reason.name == 'SAFETY':
                block_reason = "SAFETY"
                logger.warning(f"Resposta IA bloqueada por SAFETY (Disc. Eval Rigor). Razão: {block_reason}.")
                raise AIResponseError(f"Avaliação bloqueada pela API ({block_reason}).")

            if not first_candidate or not hasattr(first_candidate, 'content') or not hasattr(first_candidate.content, 'parts') or not first_candidate.content.parts:
                finish_reason = "N/A"
                if first_candidate and hasattr(first_candidate, 'finish_reason'):
                    finish_reason = first_candidate.finish_reason.name
                logger.warning(f"Resposta IA vazia/inválida (Disc. Eval Rigor). Finish Reason: {finish_reason}.")
                raise AIResponseError(f"IA retornou resposta vazia ou inválida na avaliação (Finish Reason: {finish_reason}).")

            generated_text = first_candidate.content.parts[0].text
            logger.info("Texto da avaliação (Rigor) recebido da IA.")
            logger.debug(f"Texto Recebido Completo (Eval Rigor):\n{generated_text}") # Debug opcional

            # Retorna o texto bruto para ser parseado externamente
            return generated_text

        except AIResponseError as e:
            raise e
        except Exception as e:
            logger.error(f"Erro GERAL durante chamada à API (Disc. Eval Rigor): {e}", exc_info=True)
            raise AIServiceError(f"Erro na comunicação com a API (Disc. Eval Rigor): {e}")

# --- FIM DA CLASSE ---