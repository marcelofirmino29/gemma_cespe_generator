# generator/services.py (VERSÃO COM PROMPT AJUSTADO EM generate_questions)

import logging
from django.conf import settings
import ollama 
from .models import Questao 
from .utils import parse_ai_response_to_questions, parse_evaluation_scores
from .exceptions import ConfigurationError, AIServiceError, AIResponseError, ParsingError

logger = logging.getLogger('generator')

class QuestionGenerationService:
    """
    Serviço para interagir com um modelo de linguagem via Ollama
    para geração e avaliação de questões.
    """
    def __init__(self):
        """Inicializa o serviço, configurando o cliente Ollama e o modelo."""
        self.client = None
        self.model_name = None
        self.request_timeout = 3000.0

        try:
            ollama_host = getattr(settings, 'OLLAMA_HOST', None)
            if not ollama_host:
                raise ConfigurationError("Configuração Ausente: OLLAMA_HOST não definido.")

            self.model_name = getattr(settings, 'OLLAMA_MODEL_NAME', None)
            if not self.model_name:
                raise ConfigurationError("Configuração Ausente: OLLAMA_MODEL_NAME não definido.")

            self.request_timeout = float(getattr(settings, 'OLLAMA_REQUEST_TIMEOUT', 3000.0))
            self.client = ollama.Client(host=ollama_host, timeout=self.request_timeout)
            
            try:
                logger.debug(f"Tentando listar modelos do Ollama em {ollama_host}...")
                response_data = self.client.list() 
                logger.debug(f"Resposta da API Ollama (self.client.list()): {response_data}")

                models_list_from_api = response_data.get('models', [])
                
                processed_model_names = []
                if isinstance(models_list_from_api, list):
                    for model_item in models_list_from_api:
                        model_name_str = None
                        if isinstance(model_item, dict):
                            model_name_str = model_item.get('name')
                        elif hasattr(model_item, 'name') and isinstance(getattr(model_item, 'name', None), str):
                            model_name_str = model_item.name
                        elif hasattr(model_item, 'model') and isinstance(getattr(model_item, 'model', None), str):
                            model_name_str = model_item.model
                        else:
                            logger.warning(f"Item modelo Ollama tem formato desconhecido ou falta atributo 'name'/'model': {type(model_item)} - {model_item}")

                        if model_name_str:
                            processed_model_names.append(model_name_str)
                        elif model_name_str is None and not isinstance(model_item, dict) and not (hasattr(model_item, 'name') or hasattr(model_item, 'model')):
                            pass 
                        elif model_name_str is not None and not isinstance(model_name_str, str):
                            logger.warning(f"Nome do modelo Ollama encontrado mas não é uma string: '{model_name_str}' (tipo: {type(model_name_str)}) para o item: {model_item}")
                else:
                    logger.warning(f"A chave 'models' na resposta do Ollama não continha uma lista ou era inválida. Conteúdo: {models_list_from_api}")

                logger.info(f"Nomes dos modelos Ollama processados: {processed_model_names}")

                target_base_name = self.model_name.split(':')[0]
                is_model_present_check = any(target_base_name in name_from_list for name_from_list in processed_model_names)

                if not processed_model_names:
                    logger.warning(f"Nenhum nome de modelo pôde ser processado da resposta da API Ollama. Verifique os logs de debug e warning acima.")
                
                if not is_model_present_check:
                    logger.warning(
                        f"Modelo base '{target_base_name}' (de OLLAMA_MODEL_NAME: '{self.model_name}') "
                        f"não parece estar entre os modelos disponíveis ({processed_model_names}) no Ollama em {ollama_host}. "
                        f"Certifique-se de que ele foi baixado (ex: 'ollama pull {self.model_name}'). "
                        "O serviço tentará usá-lo mesmo assim."
                    )
                else:
                     logger.info(f"Cliente Ollama inicializado. Modelo '{self.model_name}' (ou seu nome base) parece estar disponível. Host: '{ollama_host}', Timeout: {self.request_timeout}s.")

            except ollama.ResponseError as oe:
                logger.error(f"Erro de resposta da API Ollama ao listar modelos em {ollama_host}: Status {oe.status_code}, Erro: {oe.error}", exc_info=True)
                raise ConfigurationError(f"Erro da API Ollama (listar modelos) em '{ollama_host}': Status {oe.status_code}, {oe.error}")
            except ollama.RequestError as ore:
                logger.error(f"Erro de requisição ao tentar listar modelos do Ollama em {ollama_host}: {ore}", exc_info=True)
                raise ConfigurationError(f"Erro de comunicação (listar modelos) com Ollama em '{ollama_host}': {ore}")
            except Exception as conn_exc: 
                logger.error(f"Falha inesperada ao listar ou processar modelos do Ollama em {ollama_host}: {conn_exc}", exc_info=True)
                raise ConfigurationError(f"Falha ao obter/processar lista de modelos do Ollama em '{ollama_host}'. Detalhe: {conn_exc}")

        except ConfigurationError as e:
            logger.error(f"Erro de Configuração no Serviço Ollama: {e}")
            raise e
        except Exception as e:
            logger.critical(f"Falha crítica na inicialização do Serviço Ollama: {e}", exc_info=True)
            raise ConfigurationError(f"Falha na inicialização do Serviço Ollama: {e}")

    # --- MÉTODO generate_questions (PROMPT AJUSTADO) ---
    def generate_questions(self, topic, num_questions, difficulty_level='medio', area=None):
        if not self.client or not self.model_name:
            raise ConfigurationError("Serviço Ollama não inicializado corretamente.")

        prompt = (
            f"**Persona:** Você é um examinador experiente da banca Cebraspe/CESPE, elaborando itens inéditos e desafiadores.\n"
            f"**Tarefa:** Gerar um conjunto de **{num_questions} questões** (itens) no formato Certo/Errado com base nas seguintes informações:\n"
            f"    - **Área de Conhecimento Principal:** {area.nome if area else 'Geral'}\n"
            f"    - **Tópico/Contexto Específico:** '{topic}'\n"
            f"    - **Nível de Dificuldade:** {difficulty_level or 'Médio'}\n"
            f"**Estrutura OBRIGATÓRIA de Saída:**\n"
            f"1.  **UM Texto Motivador Principal:** Crie um texto conciso (3-6 frases) para contextualizar o tópico '{topic}'. Este texto será a base para TODOS os itens. Se não for possível criar um texto motivador relevante, escreva 'Texto Motivador Principal: Não aplicável'.\n"
            f"2.  **{num_questions} Itens de Julgamento:** Gere EXATAMENTE {num_questions} itens (afirmações C/E).\n"
            f"**Diretrizes para Itens:**\n"
            f"    - **Analíticos e Não Óbvios.**\n"
            f"    - **Evitar Absolutos:** Use com extrema moderação termos como 'sempre', 'nunca', 'apenas'.\n"
            f"    - **Balanceamento C/E Aleatório:** Distribua os gabaritos 'C' e 'E' de forma aleatória para os {num_questions} itens, buscando um equilíbrio aproximado.\n"
            f"    - **Gabarito e Justificativa Técnica:** Justificativa detalhada para cada item.\n"
            f"    - **Formato de Item Individual:** CADA item DEVE começar EXATAMENTE com a linha '**Item:**', seguido pela afirmação (NÃO numere os itens como '**Item 1:**', '**Item 2:**', etc.).\n\n" # NOVA DIRETRIZ
            
            f"**Formato ESTRITO de Saída (SIGA RIGOROSAMENTE):**\n"
            f"Use EXATAMENTE os marcadores em negrito, cada um em sua própria linha. O Texto Motivador aparece UMA ÚNICA VEZ no início.\n"
            f"Você DEVE gerar {num_questions} conjuntos de Item/Gabarito/Justificativa.\n"
            f"CADA conjunto completo (Item, Gabarito, Justificativa) DEVE ser separado do PRÓXIMO conjunto por uma ÚNICA linha contendo apenas '---'.\n\n"

            f"**Texto Motivador Principal:** [Substitua com o texto base contextualizador AQUI.]\n\n"

            f"**Item:** [Substitua com a afirmação C/E 1 AQUI.]\n"
            f"**Gabarito:** [C ou E]\n"
            f"**Justificativa:** [Substitua com a explicação técnica detalhada do item 1 AQUI.]\n"
            f"---\n" # Separador obrigatório

            f"**Item:** [Substitua com a afirmação C/E 2 AQUI.]\n"
            f"**Gabarito:** [C ou E]\n"
            f"**Justificativa:** [Substitua com a explicação técnica detalhada do item 2 AQUI.]\n"
            # Se num_questions for maior que 2, o modelo deve continuar este padrão.
            # A instrução abaixo reforça isso.
            f"{'---' if num_questions > 2 else ''}\n" # Adiciona outro separador se houver mais de 2 itens como exemplo
            f"(Continue este padrão rigoroso de Item, Gabarito, Justificativa, seguido por '---' entre cada conjunto, até ter gerado TODOS os {num_questions} itens. O último conjunto de Item/Gabarito/Justificativa NÃO deve ser seguido por '---'.)"
        )

        logger.info(f"Enviando requisição para Ollama (Modelo: {self.model_name}, Tópico: {topic[:50]}...) para gerar {num_questions} questões C/E.")
        
        try:
            response = self.client.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}],
            )
            generated_text = response.get('message', {}).get('content', '').strip()

            logger.info(f"Texto bruto recebido do Ollama para generate_questions ANTES do parsing:\n{generated_text}") # LOG CRUCIAL

            if not generated_text:
                logger.warning("Resposta do Ollama para generate_questions está vazia.")
                raise AIResponseError("Ollama retornou resposta vazia para geração de questões C/E.")

            logger.info("Texto C/E recebido do Ollama. Chamando parser...")
            parsed_data = self._parse_questions(generated_text)
            return parsed_data
            
        except ParsingError as e:
            logger.error(f"Erro de PARSING (Ollama C/E Balanceado): {e}", exc_info=True)
            raise ParsingError(f"Erro ao processar resposta do Ollama (C/E): {e}")
        except ollama.ResponseError as e:
            logger.error(f"Erro da API Ollama (Ollama C/E Balanceado): Status {e.status_code} - {e.error}", exc_info=True)
            raise AIServiceError(f"Erro na comunicação com Ollama (C/E): Status {e.status_code} - {e.error}")
        except Exception as e:
            logger.error(f"Erro GERAL na chamada Ollama (Ollama C/E Balanceado): {e}", exc_info=True)
            raise AIServiceError(f"Erro na comunicação com Ollama (C/E): {e}")

    def _parse_questions(self, text: str):
        """Delega o parsing C/E para a função especializada em utils.py."""
        logger.debug("Service: _parse_questions iniciando chamada a utils.parse_ai_response_to_questions")
        try:
            parsed_result = parse_ai_response_to_questions(text)
            logger.debug("Service: _parse_questions retornou de utils.parse_ai_response_to_questions com sucesso.")
            return parsed_result
        except ParsingError as e:
            logger.error(f"Erro retornado pelo parser C/E (utils.parse_ai_response_to_questions): {e}")
            raise e
        except Exception as e:
            logger.error(f"Erro inesperado ao chamar o parser C/E (utils.parse_ai_response_to_questions): {e}", exc_info=True)
            raise ParsingError(f"Erro inesperado durante o processamento da resposta C/E: {e}")

    def generate_discursive_exam_question(self, base_topic_or_context, num_aspects=3, area=None, complexity='Intermediária', language='pt-br'):
        """Gera uma questão discursiva completa com Ollama/Gemma."""
        if not self.client or not self.model_name:
            raise ConfigurationError("Serviço Ollama não inicializado corretamente.")

        prompt_parts = [
            f"**Instrução Principal:** Elabore uma questão discursiva completa e original em {language} sobre o tema ou contexto base:",
            f"'{base_topic_or_context}'\n",
            f"**Estrutura da Questão:**",
            "1. Texto(s) Motivador(es): (Opcional, use se agregar valor significativo ao contexto. Se não houver, omita esta seção ou indique 'Não aplicável').",
            "2. Comando da Questão: (Claro, objetivo, instruindo o que o candidato deve fazer).",
            f"3. Tópicos/Aspectos para Abordagem OBRIGATÓRIA: (Exatamente {num_aspects} aspectos distintos, claros e relacionados ao comando).\n",
            f"**Diretrizes para Elaboração:**",
            f"- Nível de Complexidade Desejado: '{complexity}'.",
            (f"- Considerar a Área de Conhecimento: '{area if area else 'Geral'}'.") if area else "",
            "- Foco em exigir análise, aplicação de conceitos ou argumentação, não apenas memorização.",
            "- Garantir que os aspectos sejam respondíveis com base no comando e no conhecimento esperado para a área/complexidade.",
            "\n**Formato de Saída:** Apresente a questão completa em texto corrido ou formato markdown, claramente separando Texto Motivador (se houver), Comando e Aspectos."
        ]
        prompt = "\n".join(filter(None, prompt_parts))
        logger.info(f"Enviando requisição para Ollama (Modelo: {self.model_name}) para gerar questão discursiva.")

        try:
            response = self.client.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )
            generated_text = response.get('message', {}).get('content', '').strip()

            # ADICIONE ESTE LOG PARA VER A RESPOSTA BRUTA DA IA:
            logger.info(f"Texto bruto recebido do Ollama para generate_discursive_exam_question ANTES do parsing (se houver):\n{generated_text}")

            if not generated_text:
                logger.warning("Resposta do Ollama para generate_discursive_exam_question está vazia.")
                raise AIResponseError("Ollama retornou resposta vazia para geração de questão discursiva.")
            
            logger.info("Texto da questão discursiva gerado pelo Ollama.")
            return generated_text

        except ollama.ResponseError as e:
            logger.error(f"Erro da API Ollama (Disc. Q Gen): Status {e.status_code} - {e.error}", exc_info=True)
            raise AIServiceError(f"Erro na comunicação com Ollama (Disc. Q Gen): Status {e.status_code} - {e.error}")
        except Exception as e:
            logger.error(f"Erro GERAL na chamada Ollama (Disc. Q Gen): {e}", exc_info=True)
            raise AIServiceError(f"Erro na comunicação com Ollama ao gerar questão discursiva: {e}")

    def generate_discursive_answer(self, essay_prompt, key_points=None, limit=None, area=None):
        """Gera uma resposta discursiva para um dado prompt com Ollama/Gemma."""
        if not self.client or not self.model_name:
            raise ConfigurationError("Serviço Ollama não inicializado corretamente.")

        prompt_parts = [
            f"**Instrução Principal:** Elabore uma resposta discursiva coesa, coerente e bem fundamentada para o seguinte comando/questão:",
            f"'{essay_prompt}'\n",
            (f"**Pontos-Chave a serem considerados/abordados (se fornecidos):**\n{key_points}\n" if key_points else ""),
            (f"**Limite de tamanho/formato (se especificado):** '{limit}'.\n" if limit else ""),
            (f"**Área de Conhecimento (para contexto):** '{area.nome if area else 'Geral'}'.\n" if area else ""),
            "\n**Diretrizes para a Resposta:**",
            "- Use linguagem formal e norma culta.",
            "- Estruture a resposta com introdução, desenvolvimento e conclusão.",
            "- Garanta coesão e coerência entre os parágrafos.",
            "- Se aplicável, cite fontes de forma genérica (ex: 'segundo a doutrina majoritária', 'conforme a legislação vigente') ou use conhecimentos gerais consolidados.",
            "- Respeite o limite de tamanho, se especificado."
        ]
        prompt = "\n".join(filter(None, prompt_parts))
        logger.info(f"Enviando requisição para Ollama (Modelo: {self.model_name}) para gerar resposta discursiva.")

        try:
            response = self.client.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )
            generated_text = response.get('message', {}).get('content', '').strip()
            
            # ADICIONE ESTE LOG PARA VER A RESPOSTA BRUTA DA IA:
            logger.info(f"Texto bruto recebido do Ollama para generate_discursive_answer:\n{generated_text}")

            if not generated_text:
                logger.warning("Resposta do Ollama para generate_discursive_answer está vazia.")
                raise AIResponseError("Ollama retornou resposta vazia para geração de resposta discursiva.")

            logger.info("Texto da resposta discursiva gerado pelo Ollama.")
            return generated_text

        except ollama.ResponseError as e:
            logger.error(f"Erro da API Ollama (Disc. Ans Gen): Status {e.status_code} - {e.error}", exc_info=True)
            raise AIServiceError(f"Erro na comunicação com Ollama (Disc. Ans Gen): Status {e.status_code} - {e.error}")
        except Exception as e:
            logger.error(f"Erro GERAL na chamada Ollama (Disc. Ans Gen): {e}", exc_info=True)
            raise AIServiceError(f"Erro na comunicação com Ollama ao gerar resposta discursiva: {e}")

    def evaluate_discursive_answer(self, exam_context, user_answer, line_count=None):
        """Avalia resposta discursiva com Ollama/Gemma (retorna texto bruto para parser externo)."""
        if not self.client or not self.model_name:
            raise ConfigurationError("Serviço Ollama não inicializado corretamente.")

        char_count = len(user_answer)
        min_chars = 1400 
        max_nc_value = 30.00 

        prompt_parts = [
            "**Instrução Principal:** Avalie a 'Resposta do Usuário' de forma RÍGIDA E DETALHADA versus o 'Comando da Questão'. Siga TODAS as regras:",
            "\n**Regra 1: Mínimo Caracteres:**",
            f"- Caracteres da Resposta: {char_count}. Se for menor que {min_chars} caracteres, a resposta é considerada insuficiente. Indique CLARAMENTE 'Caracteres Insuficientes' nos Comentários e atribua NPD = 0.00 (Eliminado). Ignore as demais regras de nota (NC e NE), mas FORNEÇA feedback qualitativo sobre o conteúdo existente.",
            "\n**Regra 2: Avaliação por Aspectos (Aplicável SOMENTE SE Regra 1 OK):**",
            "- Identifique CLARAMENTE os aspectos (a, b, c...) solicitados no 'Comando da Questão'.",
            "- Avalie CADA aspecto presente na 'Resposta do Usuário'.",
            "- Se um aspecto do Comando NÃO foi respondido OU a resposta sobre ele é totalmente irrelevante/incorreta, a pontuação para ESSE aspecto é ZERO.",
            "\n**Regra 3: Nota Conteúdo (NC) Proporcional (Aplicável SOMENTE SE Regra 1 OK):**",
            f"- A Nota Máxima de Conteúdo (Max NC) possível é {max_nc_value}, distribuída igualmente entre os aspectos identificados no Comando.",
            f"- Calcule a NC final proporcionalmente aos aspectos que foram BEM respondidos (com profundidade e correção adequadas). Exemplo: Se são 3 aspectos (valendo {max_nc_value/3:.2f} cada) e 2 foram BEM respondidos, a NC máxima alcançável seria {max_nc_value*2/3:.2f}. A NC final será um valor ATÉ esse máximo, dependendo da qualidade.",
            "- Na 'Justificativa NC', explique DETALHADAMENTE o cálculo: liste os aspectos do comando, indique quais foram respondidos (OK/Parcial/Não OK), como a proporcionalidade foi aplicada e justifique a nota final atribuída.",
            "\n**Regra 4: Nota Erros (NE) (Aplicável SOMENTE SE Regra 1 OK):**",
            "- Conte o número total de erros gramaticais e de norma culta (ortografia, concordância, regência, etc.) na 'Resposta do Usuário'.",
            "- O valor de NE é simplesmente essa contagem (um número inteiro).",
            "\n**Regra 5: Nota Final (NPD):**",
            f"- Se a Regra 1 falhou (Caracteres < {min_chars}), então NPD = 0.00.",
            f"- Se a Regra 1 foi OK, use a fórmula: NPD = NC - (2 * NE). O resultado não pode ser negativo (NPD mínimo é 0.00). Certifique-se que NPD seja formatado com duas casas decimais.",
            "\n**Regra 6: Feedback Geral (Comentários):**",
            "- Elabore um feedback geral sobre a resposta: qualidade da argumentação, clareza, coesão textual, atendimento geral ao comando.",
            "- Se a Regra 1 falhou, INCLUA a indicação 'Caracteres Insuficientes' neste campo.",
            "\n---",
            f"**Comando da Questão:**\n{exam_context}",
            "---",
            f"**Resposta do Usuário (Caracteres: {char_count}, Linhas: {line_count or 'N/A'}):**\n{user_answer}",
            "---",
            "**Formato OBRIGATÓRIO de Saída (Use EXATAMENTE estes marcadores em linhas separadas, sem explicações adicionais):**",
            "NC: [Valor float da NC com duas casas decimais OU 0.00 se Regra 1 falhou]",
            "NE: [Valor int de erros contados OU 0 se Regra 1 falhou]",
            "NPD: [Valor float da NPD com duas casas decimais]",
            "Justificativa NC: [Texto detalhado explicando o cálculo da NC]",
            "Comentários: [Feedback geral, incluindo 'Caracteres Insuficientes' se aplicável]"
        ]
        prompt = "\n".join(prompt_parts)
        logger.info(f"Enviando requisição para Ollama (Modelo: {self.model_name}) para avaliar resposta discursiva.")

        try:
            response = self.client.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )
            generated_text = response.get('message', {}).get('content', '').strip()

            # ADICIONE ESTE LOG PARA VER A RESPOSTA BRUTA DA IA:
            logger.info(f"Texto bruto recebido do Ollama para evaluate_discursive_answer:\n{generated_text}")
            logger.debug(f"Texto Recebido Completo (Eval Rigor):\n{generated_text}") # Seu log original

            if not generated_text:
                logger.warning("Resposta do Ollama para evaluate_discursive_answer está vazia.")
                raise AIResponseError("Ollama retornou resposta vazia para avaliação de resposta discursiva.")

            logger.info("Texto da avaliação (Rigor) recebido do Ollama.")
            return generated_text

        except ollama.ResponseError as e:
            logger.error(f"Erro da API Ollama (Disc. Eval Rigor): Status {e.status_code} - {e.error}", exc_info=True)
            raise AIServiceError(f"Erro na comunicação com Ollama (Disc. Eval Rigor): Status {e.status_code} - {e.error}")
        except Exception as e:
            logger.error(f"Erro GERAL na chamada Ollama (Disc. Eval Rigor): {e}", exc_info=True)
            raise AIServiceError(f"Erro na comunicação com Ollama (Disc. Eval Rigor): {e}")

    def get_ai_response(self, user_prompt: str) -> str:
        """
        Envia um prompt genérico do usuário para o Ollama/Gemma e retorna a resposta textual.
        """
        if not self.client or not self.model_name:
            raise ConfigurationError("Serviço Ollama não inicializado corretamente.")
        if not user_prompt:
            raise ValueError("O prompt do usuário não pode ser vazio.")

        prompt = user_prompt
        logger.info(f"Enviando requisição para Ollama (Modelo: {self.model_name}, Prompt: {prompt[:100]}...) para 'Ask AI'.")
        
        try:
            response = self.client.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )
            generated_text = response.get('message', {}).get('content', '').strip()

            # ADICIONE ESTE LOG PARA VER A RESPOSTA BRUTA DA IA:
            logger.info(f"Texto bruto recebido do Ollama para get_ai_response:\n{generated_text}")

            if not generated_text:
                logger.warning("Resposta do Ollama para get_ai_response (Ask AI) está vazia.")
                raise AIResponseError("Ollama retornou resposta vazia para 'Ask AI'.")

            logger.info("Texto (Ask AI) recebido do Ollama.")
            return generated_text

        except ollama.ResponseError as e:
            logger.error(f"Erro da API Ollama (Ask AI): Status {e.status_code} - {e.error}", exc_info=True)
            raise AIServiceError(f"Erro na comunicação com Ollama (Ask AI): Status {e.status_code} - {e.error}")
        except Exception as e:
            logger.error(f"Erro GERAL na chamada Ollama (Ask AI): {e}", exc_info=True)
            raise AIServiceError(f"Erro na comunicação com Ollama (Ask AI): {e}")