# generator/services.py (VERSÃO FINAL CORRIGIDA)

import logging
from django.conf import settings
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold, GenerationConfig
# <<< Importa os PARSERS de utils.py >>>
from .utils import parse_ai_response_to_questions, parse_evaluation_scores
# <<< Importa as EXCEÇÕES locais >>>
from .exceptions import ConfigurationError, AIServiceError, AIResponseError, ParsingError

logger = logging.getLogger('generator')

class QuestionGenerationService:
    def __init__(self):
        self.model = None
        self.generation_config = None
        self.safety_settings = None
        try:
            api_key = settings.GOOGLE_API_KEY
            if not api_key: raise ConfigurationError("GOOGLE_API_KEY não definida.")
            genai.configure(api_key=api_key)
            self.generation_config = GenerationConfig(temperature=getattr(settings, 'AI_GENERATION_TEMPERATURE', 0.7))
            model_name = getattr(settings, 'AI_MODEL_NAME', None)
            if not model_name: raise ConfigurationError("AI_MODEL_NAME não definida.")
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"Modelo '{model_name}' inicializado (Service).")
            self._load_and_convert_safety_settings()
        except AttributeError as e: missing_setting = str(e).split("'")[-2]; raise ConfigurationError(f"Config obrigatória ausente: '{missing_setting}'")
        except ConfigurationError as e: raise e
        except Exception as e: logger.critical(f"Falha init Google AI: {e}", exc_info=True); raise ConfigurationError(f"Falha init Google AI: {e}")

    def _load_and_convert_safety_settings(self):
        # ... (código inalterado) ...
        raw_settings = getattr(settings, 'GOOGLE_AI_SAFETY_SETTINGS', None)
        if not raw_settings or not isinstance(raw_settings, list): logger.warning("GOOGLE_AI_SAFETY_SETTINGS não definidas/inválidas."); self.safety_settings = None; return
        converted_settings = []; category_map = {name: member for name, member in HarmCategory.__members__.items()}; threshold_map = {name: member for name, member in HarmBlockThreshold.__members__.items()}
        try:
            for setting in raw_settings:
                if not isinstance(setting, dict): logger.warning(f"Item inválido: {setting}"); continue
                category_str = setting.get("category"); threshold_str = setting.get("threshold")
                if category_str is None or threshold_str is None: logger.warning(f"Dicionário incompleto: {setting}"); continue
                category_enum = category_map.get(category_str); threshold_enum = threshold_map.get(threshold_str)
                if category_enum is None: logger.error(f"Category inválida: '{category_str}'."); continue
                if threshold_enum is None: logger.error(f"Threshold inválido: '{threshold_str}'."); continue
                converted_settings.append({"category": category_enum, "threshold": threshold_enum})
            if converted_settings: self.safety_settings = converted_settings; logger.info(f"Safety Settings carregadas: {len(converted_settings)}."); logger.debug(f"Safety: {self.safety_settings}")
            else: logger.warning("Nenhuma safety setting válida."); self.safety_settings = None
        except Exception as e: logger.error(f"Erro processar Safety Settings: {e}", exc_info=True); raise ConfigurationError(f"Erro processar Safety Settings: {e}")

    # --- MÉTODO generate_questions (COM PROMPT "EXAMINADOR RÍGIDO") ---
    def generate_questions(self, topic, num_questions, difficulty_level='medio'):
        """
        Gera itens C/E DESAFIADORES no formato Texto Motivador + Comando + Item,
        com foco em nuances, exceções e análise crítica.
        """
        if not self.model:
            raise ConfigurationError("Serviço de IA não inicializado corretamente.")

        # <<< PROMPT "EXAMINADOR RÍGIDO" >>>
        prompt = (
            f"**Persona:** Você é um examinador de concurso público experiente, conhecido por sua **extrema rigurosidade e ceticismo**. Seu objetivo é criar itens de julgamento (Certo/Errado) **altamente desafiadores** sobre o tópico '{topic}', no nível de dificuldade '{difficulty_level}'. Você quer **separar os candidatos realmente preparados** daqueles com conhecimento superficial, testando a atenção a detalhes minuciosos, o conhecimento de **exceções às regras**, a capacidade de identificar **pegadinhas bem elaboradas** e a interpretação precisa de conceitos complexos. Sua meta é **reprovar os despreparados** através de itens tecnicamente corretos, mas que exigem raciocínio profundo.\n\n"
            f"**Instrução Principal:** Gere exatamente {num_questions} itens C/E seguindo rigorosamente as diretrizes abaixo.\n"
            f"**Diretrizes de Elaboração dos Itens:**\n"
            f"- **Dificuldade e Sutileza:** Crie afirmações (Itens) que **pareçam corretas à primeira vista**, mas contenham um erro sutil, uma condição implícita não atendida, uma generalização indevida, ou se baseiem em uma exceção pouco conhecida à regra geral.\n"
            f"- **Exploração de Nuances:** Foque em pontos controversos, detalhes específicos da legislação/doutrina/teoria, ou requisitos específicos para aplicação de um conceito.\n"
#            f"- **Evite o Óbvio e o Absoluto:** NÃO crie itens sobre fatos básicos ou definições triviais. Evite termos como 'sempre', 'nunca', 'jamais', 'totalmente', 'apenas', 'somente', 'exclusivamente', a menos que o erro do item resida justamente na aplicação incorreta ou na veracidade técnica desse termo absoluto.\n"
            f"- **Indução ao Erro (com Fundamento Técnico):** Formule itens que possam induzir ao erro um candidato com leitura rápida ou conhecimento superficial. Pode incluir informações corretas, mas irrelevantes para o julgamento central, ou omitir uma condição essencial.\n"
            f"- **Contextualização (Obrigatória):** Use **SEMPRE** um Texto Motivador longo e um Comando claro para direcionar o julgamento do item.\n"
            f"- **Gabarito Inequívoco:** Apesar da dificuldade, cada item DEVE ter um gabarito (C ou E) objetivamente correto e uma Justificativa **técnica e detalhada** que explique inequivocamente o erro ou acerto sutil, justificando por que as alternativas (C ou E) estariam incorretas e fazendo referência clara ao Texto Motivador ou Comando, se pertinente.\n\n"
            f"**Formato OBRIGATÓRIO de Saída:**\n"
            f"Para CADA UM dos {num_questions} itens, use EXATAMENTE a estrutura e os marcadores em negrito abaixo. Separe cada item completo com uma linha contendo apenas '---'.\n\n"
            f"**Texto Motivador:** [Texto curto e pertinente (1-4 frases). Pode ser fragmento de lei, julgado, teoria, cenário hipotético. Se for IMPOSSÍVEL criar um motivador relevante, escreva 'Não aplicável', mas priorize a criação.]\n"
            f"**Comando:** [Instrução clara e direta para julgar o item subsequente. Ex: 'Com base no texto, julgue o item a seguir acerca de...', 'Considerando a jurisprudência e a doutrina sobre X, julgue o item que se segue.']\n"
            f"**Item:** [A afirmação C/E desafiadora, analítica e que explore nuances.]\n"
            f"**Gabarito:** [C ou E]\n"
            f"**Justificativa:** [Explicação técnica, detalhada e precisa do gabarito, desmontando a 'pegadinha' e justificando a resposta correta.]\n"
            f"---\n"
            f"(Repita essa estrutura completa {num_questions} vezes)"
        )
        # <<< FIM DO NOVO PROMPT >>>

        # O restante do método continua igual, chamando a API e o _parse_questions
        if self.safety_settings: logger.info(f"SERVICE CALL (C/E Rígido): Usando {len(self.safety_settings)} regras.")
        else: logger.info("SERVICE CALL (C/E Rígido): Usando safety padrão.")
        try:
            logger.info(f"Enviando req (C/E Rígido) API (Modelo: {self.model._model_name}, Tópico: {topic[:50]}...)")
            response = self.model.generate_content(prompt, generation_config=self.generation_config, safety_settings=self.safety_settings)
            # ... (Verificação de Bloqueio como antes) ...
            first_candidate = response.candidates[0] if response.candidates else None
            if first_candidate and first_candidate.finish_reason.name == 'SAFETY': logger.warning(f"Resp IA bloqueada (C/E Rígido)."); raise AIResponseError(f"Geração bloqueada API.")
            elif not first_candidate or not hasattr(first_candidate.content, 'parts') or not first_candidate.content.parts: finish_reason = first_candidate.finish_reason.name if first_candidate else "N/A"; logger.warning(f"Resp IA vazia (C/E Rígido). Finish: {finish_reason}."); raise AIResponseError(f"IA retornou resp vazia (Finish: {finish_reason}).")

            generated_text = first_candidate.content.parts[0].text
            logger.info("Texto C/E Rígido recebido da IA. Chamando parser...")
            # O parser em utils.py (versão por blocos) precisa ser capaz de lidar com essa estrutura
            parsed_questions = self._parse_questions(generated_text) # Chama _parse_questions (que chama utils)
            return parsed_questions
        # ... (Blocos except como antes) ...
        except AIResponseError as e: raise e
        except ParsingError as e: logger.error(f"Erro PARSING (C/E Rígido): {e}", exc_info=True); raise ParsingError(f"Erro processar resposta IA (C/E): {e}")
        except Exception as e: logger.error(f"Erro GERAL API (C/E Rígido): {e}", exc_info=True); raise AIServiceError(f"Erro comunicação API (C/E): {e}")

    # --- Método _parse_questions DEVE chamar utils.py ---
    def _parse_questions(self, text: str) -> list:
        """Delega o parsing C/E para a função especializada em utils.py."""
        logger.debug("Service: _parse_questions chamando utils.parse_ai_response_to_questions")
        try: return parse_ai_response_to_questions(text) # Usa a função do utils.py
        except ParsingError as e: logger.error(f"Erro retornado por parser C/E: {e}"); raise e
        except Exception as e: logger.error(f"Erro inesperado ao chamar parser C/E: {e}", exc_info=True); raise ParsingError(f"Erro inesperado no processamento C/E: {e}")

    # --- MÉTODO generate_discursive_exam_question (Inalterado) ---
    def generate_discursive_exam_question(self, base_topic_or_context, num_aspects=3, area=None, complexity='Intermediária', language='pt-br'):
        # ... (código como antes) ...
        if not self.model: raise ConfigurationError("Serviço IA não inicializado.")
        prompt_parts = [f"**Instrução:** Elabore questão discursiva ({language}) sobre:", f"'{base_topic_or_context}'\n", f"**Estrutura:**", "1. Texto(s) Motivador(es): (Se aplicável).", "2. Comando:", f"3. Aspectos: ({num_aspects}).\n", f"**Diretrizes:** Complexidade: '{complexity}'.", (f"Área: '{area}'." if area else ""), "- Foco em análise.", "\n**Formato:** Texto corrido/markdown."]
        prompt = "\n".join(filter(None, prompt_parts))
        if self.safety_settings: logger.info(f"SERVICE CALL (Disc. Q): Usando {len(self.safety_settings)} regras.")
        else: logger.info("SERVICE CALL (Disc. Q): Usando safety padrão.")
        try:
            logger.info(f"Enviando req (Disc. Q) API (Modelo: {self.model._model_name})")
            response = self.model.generate_content(prompt, generation_config=self.generation_config, safety_settings=self.safety_settings)
            first_candidate = response.candidates[0] if response.candidates else None
            if first_candidate and first_candidate.finish_reason.name == 'SAFETY': block_reason = "SAFETY"; logger.warning(f"Resposta IA bloqueada (Disc. Q). Razão: {block_reason}."); raise AIResponseError(f"Geração questão bloqueada ({block_reason}).")
            elif not first_candidate or not hasattr(first_candidate.content, 'parts') or not first_candidate.content.parts: finish_reason = first_candidate.finish_reason.name if first_candidate else "N/A"; logger.warning(f"Resposta IA vazia/inválida (Disc. Q). Finish: {finish_reason}."); raise AIResponseError(f"IA retornou resp vazia/inválida (Finish: {finish_reason}).")
            generated_text = first_candidate.content.parts[0].text; logger.info("Texto questão discursiva gerado IA."); return generated_text
        except AIResponseError as e: raise e
        except Exception as e: logger.error(f"Erro API (Disc. Q): {e}", exc_info=True); raise AIServiceError(f"Erro comunicação API (Disc. Q): {e}")

    # --- MÉTODO generate_discursive_answer (Inalterado) ---
    def generate_discursive_answer(self, essay_prompt, key_points=None, limit=None, area=None):
        # ... (código como antes) ...
        if not self.model: raise ConfigurationError("Serviço IA não inicializado.")
        prompt_parts = [f"**Instrução:** Elabore resposta discursiva para:", f"'{essay_prompt}'\n", (f"**Pontos-Chave:**\n{key_points}\n" if key_points else ""), (f"**Limite:** '{limit}'.\n" if limit else ""), (f"**Área:** '{area}'.\n" if area else ""), "\n**Diretrizes:**", "- Linguagem formal.", "- Coesão.", "- Citar fontes (genérico)."]
        prompt = "\n".join(filter(None, prompt_parts))
        if self.safety_settings: logger.info(f"SERVICE CALL (Disc. Ans): Usando {len(self.safety_settings)} regras.")
        else: logger.info("SERVICE CALL (Disc. Ans): Usando safety padrão.")
        try:
            logger.info(f"Enviando req (Disc. Ans) API (Modelo: {self.model._model_name})")
            response = self.model.generate_content(prompt, generation_config=self.generation_config, safety_settings=self.safety_settings)
            first_candidate = response.candidates[0] if response.candidates else None
            if first_candidate and first_candidate.finish_reason.name == 'SAFETY': block_reason = "SAFETY"; logger.warning(f"Resposta IA bloqueada (Disc. Ans). Razão: {block_reason}."); raise AIResponseError(f"Geração resposta bloqueada ({block_reason}).")
            elif not first_candidate or not hasattr(first_candidate.content, 'parts') or not first_candidate.content.parts: finish_reason = first_candidate.finish_reason.name if first_candidate else "N/A"; logger.warning(f"Resposta IA vazia/inválida (Disc. Ans). Finish: {finish_reason}."); raise AIResponseError(f"IA retornou resp vazia/inválida (Finish: {finish_reason}).")
            generated_text = first_candidate.content.parts[0].text; logger.info("Texto resposta discursiva gerado IA."); return generated_text
        except AIResponseError as e: raise e
        except Exception as e: logger.error(f"Erro API (Disc. Ans): {e}", exc_info=True); raise AIServiceError(f"Erro comunicação API (Disc. Ans): {e}")

    # --- MÉTODO evaluate_discursive_answer (Com prompt RÍGIDO) ---
    def evaluate_discursive_answer(self, exam_context, user_answer, line_count=None):
        """Avalia resposta discursiva com regras RÍGIDAS."""
        if not self.model: raise ConfigurationError("Serviço IA não inicializado.")
        char_count = len(user_answer); min_chars = 1400
        prompt_parts = [
            "**Instrução Principal:** Avalie a 'Resposta do Usuário' de forma RÍGIDA E DETALHADA vs 'Comando da Questão'. Siga TODAS as regras:",
            "\n**Regra 1: Mínimo Caracteres:**", f"- Chars: {char_count}. Se < {min_chars}, é insuficiente. Indique e NPD = 0.00 (Eliminado). Ignore demais regras de nota, mas dê feedback.",
            "\n**Regra 2: Avaliação por Aspectos (Se Regra 1 OK):**", "- Identifique aspectos (a, b, c...) no Comando.", "- Avalie CADA aspecto.", "- Se aspecto NÃO respondido ou irrelevante, pontuação do aspecto = ZERO.",
            "\n**Regra 3: Nota Conteúdo (NC) Proporcional (Se Regra 1 OK):**", f"- Max NC = 30.00 distribuída entre aspectos.", "- Calcule NC proporcional aos aspectos BEM respondidos. Ex: 3 aspectos (10pts cada), 2 OK -> NC max = 20.00.", "- NC final reflete profundidade/correção dos aspectos respondidos.", "- JUSTIFIQUE DETALHADAMENTE cálculo da NC (aspectos OK/Não OK, proporcionalidade).",
            "\n**Regra 4: Erros (NE) (Se Regra 1 OK):**", "- Conte erros gramaticais/norma culta.",
            "\n**Regra 5: Nota Final (NPD) (Se Regra 1 OK):**", "- Use: NPD = NC - (2 * NE) (mínimo 0).", "- Se Regra 1 falhou, NPD = 0.00.",
            "\n**Regra 6: Feedback Geral:**", "- Comente qualidade, clareza, coesão, atendimento geral.",
            "\n---", f"**Comando da Questão:**\n{exam_context}", "---", f"**Resposta do Usuário (Chars: {char_count}, Linhas: {line_count or 'N/A'}):**\n{user_answer}", "---",
            "**Formato OBRIGATÓRIO Saída:** Use marcadores exatos em linhas separadas:",
            "NC: [Valor float NC Regra 3]", "NE: [Valor int NE Regra 4]", "NPD: [Valor float NPD Regra 5 ou 0.00 Regra 1]",
            "Justificativa NC: [Texto detalhado cálculo NC Regra 3]", "Comentários: [Feedback geral Regra 6 + Info Regra 1 se aplicável]"
        ]
        prompt = "\n".join(prompt_parts)
        if self.safety_settings: logger.info(f"SERVICE CALL (Disc. Eval Rigor): Usando {len(self.safety_settings)} regras.")
        else: logger.info("SERVICE CALL (Disc. Eval Rigor): Usando safety padrão.")
        try:
            logger.info(f"Enviando req (Disc. Eval Rigor) API (Modelo: {self.model._model_name})")
            # Removido log do prompt inteiro por verbosidade, mantido início no DEBUG da view
            # logger.debug(f"Prompt enviado (início): {prompt[:500]}...")
            response = self.model.generate_content(prompt, generation_config=self.generation_config, safety_settings=self.safety_settings)
            first_candidate = response.candidates[0] if response.candidates else None
            if first_candidate and first_candidate.finish_reason.name == 'SAFETY': block_reason = "SAFETY"; logger.warning(f"Resposta IA bloqueada (Disc. Eval Rigor). Razão: {block_reason}."); raise AIResponseError(f"Avaliação bloqueada API ({block_reason}).")
            elif not first_candidate or not hasattr(first_candidate.content, 'parts') or not first_candidate.content.parts: finish_reason = first_candidate.finish_reason.name if first_candidate else "N/A"; logger.warning(f"Resposta IA vazia/inválida (Disc. Eval Rigor). Finish: {finish_reason}."); raise AIResponseError(f"IA retornou resp vazia/inválida (Finish: {finish_reason}).")
            generated_text = first_candidate.content.parts[0].text; logger.info("Texto avaliação (Rigor) recebido IA."); logger.debug(f"Texto Recebido Completo (Eval Rigor):\n{generated_text}"); return generated_text
        except AIResponseError as e: raise e
        except Exception as e: logger.error(f"Erro API (Disc. Eval Rigor): {e}", exc_info=True); raise AIServiceError(f"Erro comunicação API (Disc. Eval Rigor): {e}")

# --- FIM DA CLASSE ---