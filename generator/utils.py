# generator/utils.py
import re
from .exceptions import ParsingError
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FUNÇÃO 1: Parsing C/E (REESCRITA para Novo Formato: Motivador, Comando, Item)
# ---------------------------------------------------------------------------
def parse_ai_response_to_questions(text: str) -> list[dict]:
    """
    Faz o parsing do texto bruto da IA para extrair questões C/E estruturadas
    no formato Texto Motivador / Comando / Item / Gabarito / Justificativa,
    separadas por '---'.
    Retorna lista de dicionários: [{'afirmacao': <texto do Item>, 'gabarito': <C/E>, 'justificativa': <texto>, 'texto_motivador': <texto ou None>}]
    """
    if not text:
        logger.warning("Parser C/E (Novo Formato): Texto vazio recebido.")
        return []

    logger.info("Parser C/E (Novo Formato): Iniciando parsing por blocos...")
    questions = []
    # Divide por '---' entre os itens completos
    blocks = [block.strip() for block in re.split(r'\n---\n?', text.strip()) if block.strip()]

    if not blocks:
        logger.error("Parser C/E (Novo Formato): Nenhum bloco encontrado após dividir por '---'.")
        return []

    logger.info(f"Parser C/E (Novo Formato): Encontrados {len(blocks)} blocos.")

    for i, block in enumerate(blocks):
        logger.debug(f"Parser C/E (Novo Formato): Processando Bloco {i+1}...")
        q = {}

        # Expressões Regulares para o NOVO formato (com marcadores em negrito opcionais)
        # Usam DOTALL para abranger múltiplas linhas e IGNORECASE
        # Capturam o conteúdo após o marcador até o início do próximo marcador conhecido ou fim do bloco
        motivador_match = re.search(r"\*?\*?Texto Motivador:\*?\*?\s*(.*?)(?=\n\s*\*\*?Comando:\*?\*?|$)", block, re.IGNORECASE | re.DOTALL)
        comando_match = re.search(r"\*?\*?Comando:\*?\*?\s*(.*?)(?=\n\s*\*\*?Item:\*?\*?|$)", block, re.IGNORECASE | re.DOTALL)
        item_match = re.search(r"\*?\*?Item:\*?\*?\s*(.*?)(?=\n\s*\*\*?Gabarito:\*?\*?|$)", block, re.IGNORECASE | re.DOTALL)
        gabarito_match = re.search(r"\*?\*?Gabarito:\*?\*?\s*(C|E)\b", block, re.IGNORECASE) # Busca C ou E explícito
        justificativa_match = re.search(r"\*?\*?Justificativa:\*?\*?\s*(.*)", block, re.IGNORECASE | re.DOTALL) # Pega até o fim do bloco

        # Extração e Validação
        if item_match:
            q['afirmacao'] = item_match.group(1).strip() # Salva o 'Item' como 'afirmacao' para manter compatibilidade com a view
        else:
            logger.warning(f"Parser C/E Bloco {i+1}: Marcador '**Item:**' não encontrado ou sem conteúdo. Bloco ignorado:\n{block}")
            continue

        if gabarito_match:
            q['gabarito'] = gabarito_match.group(1).strip().upper()
        else:
            logger.warning(f"Parser C/E Bloco {i+1}: Marcador '**Gabarito:**' (C ou E) não encontrado. Item ignorado.")
            continue

        # Campos opcionais ou informativos
        if motivador_match:
            motivador_text = motivador_match.group(1).strip()
            if motivador_text.lower() != 'não aplicável':
                q['texto_motivador'] = motivador_text
                logger.debug(f"Parser C/E Bloco {i+1}: Texto Motivador encontrado.")
            else:
                 q['texto_motivador'] = None
                 logger.debug(f"Parser C/E Bloco {i+1}: Texto Motivador marcado como 'Não aplicável'.")
        else:
             q['texto_motivador'] = None # Ou string vazia? None parece melhor.
             logger.debug(f"Parser C/E Bloco {i+1}: Texto Motivador não encontrado.")

        if justificativa_match:
            q['justificativa'] = justificativa_match.group(1).strip()
            logger.debug(f"Parser C/E Bloco {i+1}: Justificativa encontrada.")
        else:
            q['justificativa'] = None
            logger.debug(f"Parser C/E Bloco {i+1}: Justificativa não encontrada (marcador não presente?).")

        # O 'Comando' não está sendo salvo no model Questao por enquanto, apenas extraído se necessário para validação aqui
        if not comando_match:
             logger.warning(f"Parser C/E Bloco {i+1}: Marcador '**Comando:**' não encontrado.")

        questions.append(q)
        logger.debug(f"Parser C/E Bloco {i+1}: Item adicionado ao resultado: {q}")

    if not questions and blocks:
        logger.error("Parser C/E (Novo Formato): Nenhum bloco pôde ser parseado com sucesso (Item+Gabarito).")
        # Não levanta erro, view tratará lista vazia
        return []
    elif not questions:
         logger.warning("Parser C/E (Novo Formato): Nenhuma questão extraída.")
         return []

    logger.info(f"Parser C/E (Novo Formato): Parsing finalizado. Questões válidas extraídas: {len(questions)}")
    return questions

# ---------------------------------------------------------------------------
# FUNÇÃO 2: Parsing para Avaliação Discursiva (Mantida como antes)
# ---------------------------------------------------------------------------
def parse_evaluation_scores(text: str) -> dict:
    # ... (Código da função parse_evaluation_scores CORRETO como na resposta das 10:02 PM) ...
    if not text: logger.warning("Parser Avaliação: Texto vazio."); return {'NC': None, 'NE': None, 'NPD': None, 'Justificativa_NC': None, 'Comentários': None}
    logger.info("Parser Avaliação: Iniciando parsing..."); scores = {'NC': None, 'NE': None, 'NPD': None, 'Justificativa_NC': None, 'Comentários': None}
    NC_PATTERN = r"\*?\*?NC:\*?\*?\s*([+-]?\d+(?:\.\d+)?)"
    NE_PATTERN = r"\*?\*?NE:\*?\*?\s*(\d+)"
    NPD_PATTERN = r"\*?\*?NPD:\*?\*?\s*([+-]?\d+(?:\.\d+)?)"
    JUST_NC_PATTERN = r"\*?\*?Justificativa NC:\*?\*?\s*(.*?)(?=\n\s*\*\*?(?:Comentários?:\*?\*?)|$)"
    COMM_PATTERN = r"\*?\*?Comentários?:\*?\*?\s*(.*?)(?=\n\s*\*?\*?[\w\s()]+:\*?\*?|$)"
    try:
        nc_match = re.search(NC_PATTERN, text, re.I); # ... (lógica if/try/except para NC como antes) ...
        ne_match = re.search(NE_PATTERN, text, re.I); # ... (lógica if/try/except para NE como antes) ...
        npd_match = re.search(NPD_PATTERN, text, re.I); # ... (lógica if/try/except para NPD como antes) ...
        just_nc_match = re.search(JUST_NC_PATTERN, text, re.I | re.S); # ... (lógica if/try/except para Justificativa_NC) ...
        comm_match = re.search(COMM_PATTERN, text, re.I | re.S); # ... (lógica if/try/except para Comentários) ...
    except Exception as e: logger.error(f"Erro inesperado parser avaliação: {e}", exc_info=True); scores['Comentários'] = f"Erro parser: {e}"
    scores.setdefault('NC', None); scores.setdefault('NE', None); scores.setdefault('NPD', None); scores.setdefault('Justificativa_NC', None); scores.setdefault('Comentários', None)
    logger.info(f"Parser Avaliação: Parsing concluído. Resultado: {scores}"); return scores