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
            temperature = getattr(settings, 'AI_GENERATION_TEMPERATURE', 1.0)
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
# Dentro da classe QuestionGenerationService em generator/services.py

    # --- MÉTODO generate_questions (COM BALANCEAMENTO C/E REFORÇADO) ---
    def generate_questions(self, topic, num_questions, difficulty_level='medio', area=None):
        """
        Gera 1 Texto Motivador + N Itens C/E estilo Cebraspe/CESPE,
        considerando a área e buscando balanceamento C/E aleatório.
        """
        if not self.model:
            raise ConfigurationError("Serviço de IA não inicializado corretamente.")

        # <<< PROMPT REFINADO PARA BALANCEAMENTO E CLAREZA >>>
        prompt = (
            f"**Persona:** Você é um examinador experiente da banca Cebraspe/CESPE, elaborando itens inéditos e desafiadores.\n"
            f"**Tarefa:** Gerar um conjunto de questões Certo/Errado com base nas seguintes informações:\n"
            f"    - **Área de Conhecimento Principal:** {area.nome if area else 'Geral'}\n"
            f"    - **Tópico/Contexto Específico:** '{topic}'\n"
            f"    - **Nível de Dificuldade:** {difficulty_level or 'Médio'}\n" # Trata None
            f"    - **Número Total de Itens:** {num_questions}\n"
            f"**Estrutura OBRIGATÓRIA:**\n"
            f"1.  **UM Texto Motivador Principal:** Crie um texto conciso (3-6 frases) que defina ou contextualize o tópico '{topic}' dentro da área '{area.nome if area else 'Geral'}'. Este texto será a base para TODOS os itens. Se o tópico já for um texto adequado, use-o. Se não for possível, escreva 'Não aplicável'.\n"
            f"2.  **{num_questions} Itens de Julgamento:** Gere {num_questions} itens (afirmações C/E) que explorem nuances, aplicações, exceções ou consequências do conceito no motivador, relevantes para a Área.\n"
            f"**Diretrizes para Itens:**\n"
            f"    - **Analíticos e Não Óbvios:** Exigir análise e conhecimento de detalhes.\n"
            f"    - **Evitar Absolutos:** RESTRINJA AO MÁXIMO termos como 'sempre', 'nunca', 'apenas'. Prefira condições/exceções.\n"
            f"    - **Mistura de Conceitos:** Se aplicável, crie itens ERRADOS misturando conceitos similares e explique na justificativa.\n"
            # <<< DIRETRIZ DE BALANCEAMENTO REFORÇADA >>>
            f"    - **Balanceamento C/E Aleatório:** Para o lote total de {num_questions} itens, distribua os gabaritos 'C' e 'E' de forma **aleatória**, buscando um equilíbrio (quantidade **aproximadamente igual** de C e E). NÃO crie um padrão previsível.\n"
            f"    - **Gabarito Inequívoco e Justificativa Técnica:** Justificativa detalhada referenciando o motivador se necessário.\n\n"
            f"**Formato ESTRITO de Saída (SEM QUEBRAS INDESEJADAS):**\n"
            f"Use EXATAMENTE os marcadores em negrito em linhas separadas. O Texto Motivador aparece SÓ UMA VEZ no início. Separe itens completos APENAS com uma linha contendo '---'.\n\n"
            f"**Texto Motivador Principal:** [O texto base contextualizador AQUI.]\n\n"
            f"**Item:** [Afirmação C/E 1 relacionada ao Motivador e à Área.]\n"
            f"**Gabarito:** [C ou E]\n"
            f"**Justificativa:** [Explicação técnica detalhada do item 1.]\n"
            f"---\n"
            f"**Item:** [Afirmação C/E 2 relacionada ao Motivador e à Área.]\n"
            f"**Gabarito:** [C ou E]\n"
            f"**Justificativa:** [Explicação técnica detalhada do item 2.]\n"
            f"---\n"
            f"(Continue APENAS com Item/Gabarito/Justificativa para os {num_questions} itens totais)"
        )
        # <<< FIM DO PROMPT >>>

        # O restante do método continua igual...
        if self.safety_settings: logger.info(f"SERVICE CALL (C/E Balanceado v2): Usando {len(self.safety_settings)} regras.")
        else: logger.info("SERVICE CALL (C/E Balanceado v2): Usando safety padrão.")
        try:
            model_name_info = self.model._model_name if hasattr(self.model, '_model_name') else 'N/A'
            logger.info(f"Enviando req (C/E Balanceado v2) API (Modelo: {model_name_info}, Tópico: {topic[:50]}...)")

            response = self.model.generate_content(prompt, generation_config=self.generation_config, safety_settings=self.safety_settings)
            # ... (Verificação de Bloqueio como antes) ...
            first_candidate = response.candidates[0] if response.candidates else None
            if first_candidate and first_candidate.finish_reason.name == 'SAFETY': logger.warning(f"Resp IA bloqueada (C/E Balanceado v2)."); raise AIResponseError(f"Geração bloqueada API.")
            elif not first_candidate or not hasattr(first_candidate.content, 'parts') or not first_candidate.content.parts: finish_reason = first_candidate.finish_reason.name if first_candidate else "N/A"; logger.warning(f"Resp IA vazia (C/E Balanceado v2). Finish: {finish_reason}."); raise AIResponseError(f"IA retornou resp vazia (Finish: {finish_reason}).")

            generated_text = first_candidate.content.parts[0].text
            logger.info("Texto C/E (Balanceado v2) recebido da IA. Chamando parser...")
            parsed_data = self._parse_questions(generated_text) # Chama _parse_questions (que chama utils)
            return parsed_data
        except AIResponseError as e: raise e
        except ParsingError as e: logger.error(f"Erro PARSING (C/E Balanceado v2): {e}", exc_info=True); raise ParsingError(f"Erro processar resposta IA (C/E): {e}")
        except Exception as e: logger.error(f"Erro GERAL API (C/E Balanceado v2): {e}", exc_info=True); raise AIServiceError(f"Erro comunicação API (C/E): {e}")

    # --- Método _parse_questions (DEVE chamar utils.py) ---
    def _parse_questions(self, text: str):
        """Delega o parsing C/E para a função especializada em utils.py."""
        logger.debug("Service: _parse_questions chamando utils.parse_ai_response_to_questions")
        try:
            # A função em utils.py agora precisa retornar (motivador, lista_questoes)
            return parse_ai_response_to_questions(text)
        except ParsingError as e: logger.error(f"Erro retornado por parser C/E: {e}"); raise e
        except Exception as e: logger.error(f"Erro inesperado ao chamar parser C/E: {e}", exc_info=True); raise ParsingError(f"Erro inesperado no processamento C/E: {e}")

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