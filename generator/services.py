# generator/services.py
import logging
import time
from django.conf import settings
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold, GenerationConfig
from google.api_core import exceptions
from .utils import parse_ai_response_to_questions, parse_evaluation_scores
from .exceptions import ConfigurationError, AIServiceError, AIResponseError

logger = logging.getLogger('generator')

class QuestionGenerationService:
    def __init__(self):
        """Inicializa o serviço IA (Escala 100 e Cálculo Rigoroso)."""
        self.model = None
        self.generation_config = None
        self.safety_settings = None
        try:
            api_key = settings.GOOGLE_API_KEY
            if not api_key:
                raise ConfigurationError("GOOGLE_API_KEY não definida.")
            genai.configure(api_key=api_key)

            temperature = getattr(settings, 'AI_GENERATION_TEMPERATURE', 1.0)
            self.generation_config = GenerationConfig(temperature=temperature)

            model_name = getattr(settings, 'AI_MODEL_NAME', 'gemini-2.0-flash')
            self.model = genai.GenerativeModel(model_name)
            self._load_and_convert_safety_settings()
            logger.info(f"Modelo '{model_name}' pronto para Escala 100.")

        except Exception as e:
            logger.critical(f"Falha inicialização IA: {e}")
            raise ConfigurationError(f"Erro no serviço IA: {e}")

    def _load_and_convert_safety_settings(self):
        raw_settings = getattr(settings, 'GOOGLE_AI_SAFETY_SETTINGS', None)
        if not raw_settings or not isinstance(raw_settings, list):
            self.safety_settings = None
            return
        converted = []
        cat_map = {name: member for name, member in HarmCategory.__members__.items()}
        thr_map = {name: member for name, member in HarmBlockThreshold.__members__.items()}
        for s in raw_settings:
            c = cat_map.get(s.get("category"))
            t = thr_map.get(s.get("threshold"))
            if c and t: converted.append({"category": c, "threshold": t})
        self.safety_settings = converted

# generator/services.py

    def _generate_with_retry(self, prompt, retries=5, delay=35):
        """
        Lida com erros de cota (429) automaticamente.
        Aumentado para 5 retentativas com 35 segundos de intervalo para respeitar o limite 
        do plano free do Gemini (250k tokens/min e reset de janela).
        """
        for i in range(retries):
            try:
                # Chama a API do Google Generative AI
                response = self.model.generate_content(
                    prompt, 
                    generation_config=self.generation_config, 
                    safety_settings=self.safety_settings
                )
                
                # Verifica se há candidatos na resposta
                if not response.candidates:
                    raise AIResponseError("IA não retornou conteúdo.")
                
                # Verifica se a resposta foi bloqueada por segurança
                if response.candidates[0].finish_reason.name == 'SAFETY':
                    raise AIResponseError("Resposta bloqueada pelas configurações de segurança da API.")

                return response.candidates[0].content.parts[0].text

            except exceptions.ResourceExhausted:
                # Erro 429: Limite de cota atingido
                if i < retries - 1:
                    logger.warning(f"Cota atingida (429). Retentativa {i+1}/{retries} em {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error("Cota API esgotada após todas as tentativas.")
                    raise AIServiceError("A cota da API foi excedida. Por favor, aguarde cerca de 1 minuto antes de tentar novamente.")

            except exceptions.InvalidArgument as e:
                # Erro comum quando o prompt é muito grande (ex: PDF gigante)
                logger.error(f"Erro de argumento inválido (possível excesso de tokens): {e}")
                raise AIServiceError("O conteúdo enviado é muito grande para ser processado de uma vez.")

            except Exception as e:
                logger.error(f"Erro inesperado na chamada da API: {e}", exc_info=True)
                raise AIServiceError(f"Erro na comunicação com o serviço de IA: {e}")

    def generate_questions(self, topic, num_questions, difficulty_level='medio', area=None):
        """
        Gera itens Certo/Errado com formato rígido, sem numeração e balanceamento entre C e E.
        """
        area_nome = area.nome if area else 'Geral'
        
        # Prompt otimizado com instruções para remover numerações
        prompt = (
            f"Persona: Atue como um examinador experiente da banca Cebraspe/CESPE.\n"
            f"Tarefa: Elabore {num_questions} itens inéditos do tipo CERTO ou ERRADO.\n"
            f"Área de Conhecimento: {area_nome}\n"
            f"Tópico Base: {topic}\n"
            f"Nível de Dificuldade: {difficulty_level}\n\n"
            "DIRETRIZES OBRIGATÓRIAS:\n"
            "1. Gere afirmações curtas e objetivas que exijam julgamento.\n"
            "2. Distribua os gabaritos de forma equilibrada (metade Certo, metade Errado) de forma aleatória.\n"
            "3. NÃO utilize numeração nos itens (Exemplo: use apenas 'Item:', nunca 'Item 1:' ou 'Afirmação 1:').\n"
            "4. NÃO inclua números, letras ou contagens antes das frases dos itens.\n"
            "5. Não escreva textos discursivos ou pedidos de redação.\n\n"
            "FORMATO ESTRITO DE SAÍDA (Siga exatamente isto):\n"
            "Texto Motivador: [Escreva aqui um texto contextualizador de 3 a 5 frases]\n"
            "---\n"
            "Item: [Afirmação sem número ou prefixo]\n"
            "Gabarito: [C ou E]\n"
            "Justificativa: [Explicação técnica concisa]\n"
            "---\n"
            "Item: [Próxima afirmação sem número]\n"
            "Gabarito: [C ou E]\n"
            "Justificativa: [Explicação técnica concisa]\n"
        )
        
        # Chama a função de retry configurada com delay de 25s-35s
        text = self._generate_with_retry(prompt)
        
        # Log para depuração de tamanho de resposta
        logger.info(f"IA gerou resposta C/E para área {area_nome}. Tamanho: {len(text)} caracteres.")
        
        # Retorna o processamento feito pelo parser no utils.py
        return parse_ai_response_to_questions(text)

    def generate_discursive_exam_question(self, base_topic_or_context, num_aspects=3, area=None, complexity='Intermediária', language='pt-br'):
        """Gera questão discursiva estruturada."""
        prompt = (
            f"Elabore uma questão discursiva estilo Cespe sobre: '{base_topic_or_context}'.\n"
            "Estrutura: ## Contexto (Cenário); ## Comando (Itens a, b, c).\n"
            "Saída: Apenas texto Markdown com cabeçalhos claros."
        )
        return self._generate_with_retry(prompt)

    def evaluate_discursive_answer(self, exam_context, user_answer, line_count=None):
        """Avalia com escala 100 e fórmula: NPD = NC - (2 * NE / TL)."""
        tl = int(line_count) if (line_count and int(line_count) > 0) else 1
        max_nc = 100.00

        prompt = [
            "**Instrução Principal:** Avalie de forma RÍGIDA seguindo o padrão Cebraspe.",
            f"\n**1. Conteúdo (NC):** Escala de 0 a {max_nc}. Distribua os 100 pontos nos aspectos.",
            f"**2. Erros (NE):** Conte cada erro gramatical.",
            f"**3. Nota Final (NPD):** Use OBRIGATORIAMENTE a fórmula: NPD = NC - (2 * NE / {tl}).",
            "\n**4. FORMATO (FIM DO BLOCÃO):** USE PARÁGRAFOS E BULLETS. Linhas em branco entre tópicos.",
            "\n---",
            f"**Comando:** {exam_context}",
            f"**Resposta (Linhas: {tl}):** {user_answer}",
            "---",
            "**Saída OBRIGATÓRIA:**",
            "NC: [Valor]",
            "NE: [Valor]",
            "NPD: [Valor]",
            "Justificativa NC: [Texto em parágrafos]",
            "Comentários: [Análise qualitativa]"
        ]
        return self._generate_with_retry("\n".join(prompt))

    def generate_discursive_answer(self, essay_prompt, key_points=None, limit=None, area=None):
        return self._generate_with_retry(f"Sugira uma resposta para: {essay_prompt}")

    def get_ai_response(self, user_prompt: str) -> str:
        return self._generate_with_retry(user_prompt)