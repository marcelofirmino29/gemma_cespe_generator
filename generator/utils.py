# generator/utils.py
import re
from .exceptions import ParsingError
import logging


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FUNÇÃO 1: Parsing C/E (REESCRITA para: 1 Motivador + N Itens)
# ---------------------------------------------------------------------------
def parse_ai_response_to_questions(text: str) -> tuple[str | None, list[dict]]:
    """
    Faz o parsing do texto C/E no formato: 1 Motivador Principal + N Itens.
    Itens são separados por '---'. Marcadores esperados em negrito opcional.

    Retorna:
        Uma tupla: (texto_motivador_principal, lista_de_questoes)
        onde texto_motivador_principal pode ser None ou string.
        lista_de_questoes é [{afirmacao, gabarito, justificativa}, ...].
    """
    if not text: logger.warning("Parser C/E (Motivador+Itens): Texto vazio."); return None, []
    logger.info("Parser C/E (Motivador+Itens): Iniciando parsing...")

    main_motivador = None
    questions = []
    text_cleaned = text.strip()

    # 1. Tenta extrair o Texto Motivador Principal do início
    motivador_regex = r"\*?\*?Texto Motivador(?: Principal)?:\*?\*?\s*(.*?)(?=\n\n\*?\*?Item:\*?\*?|\n\s*---|$)"
    motivador_match = re.search(motivador_regex, text_cleaned, re.IGNORECASE | re.DOTALL)
    remaining_text = text_cleaned # Texto que sobra após remover o motivador

    if motivador_match:
        motivador_text = motivador_match.group(1).strip()
        if motivador_text.lower() != 'não aplicável':
            main_motivador = motivador_text
            logger.info(f"Parser C/E: Texto Motivador Principal encontrado ({len(main_motivador)} chars).")
        else:
            logger.info("Parser C/E: Texto Motivador Principal marcado como 'Não aplicável'.")
        # Remove o bloco do motivador (e marcadores seguintes) do texto a ser processado para itens
        remaining_text = text_cleaned[motivador_match.end():].strip()
    else:
        logger.warning("Parser C/E: Marcador '**Texto Motivador Principal:**' não encontrado no início.")
        # Assume que não há motivador principal e tenta parsear itens do texto todo

    # 2. Processa os blocos de Itens restantes (separados por ---)
    item_blocks = [block.strip() for block in re.split(r'\s*---\s*', remaining_text) if block.strip()]

    if not item_blocks:
        logger.error("Parser C/E: Nenhum bloco de Item encontrado após Texto Motivador (ou no texto todo).")
        # Retorna motivador (se achou) e lista vazia
        return main_motivador, []

    logger.info(f"Parser C/E: Encontrados {len(item_blocks)} blocos de Item.")

    for i, block in enumerate(item_blocks):
        logger.debug(f"Parser C/E: Processando Bloco de Item {i+1}...")
        q = {}

        # Regex para Item, Gabarito, Justificativa DENTRO do bloco do item
        # Ignora o 'Comando:' que estava no prompt, pois não salvamos ainda
        item_match = re.search(r"\*?\*?Item:\*?\*?\s*(.*?)(?=\n\s*\*\*?Gabarito:\*?\*?|$)", block, re.IGNORECASE | re.DOTALL)
        gabarito_match = re.search(r"\*?\*?Gabarito:\*?\*?\s*(C|E)\b", block, re.IGNORECASE)
        justificativa_match = re.search(r"\*?\*?Justificativa:\*?\*?\s*(.*)", block, re.IGNORECASE | re.DOTALL)

        if item_match: q['afirmacao'] = item_match.group(1).strip()
        else: logger.warning(f"Parser C/E Item Bloco {i+1}: '**Item:**' não encontrado."); continue

        if gabarito_match: q['gabarito'] = gabarito_match.group(1).strip().upper()
        else: logger.warning(f"Parser C/E Item Bloco {i+1}: '**Gabarito:**' não encontrado."); continue

        if q['gabarito'] not in ['C', 'E']: logger.warning(f"Parser C/E Item Bloco {i+1}: Gabarito inválido ('{q['gabarito']}')."); continue

        if justificativa_match: q['justificativa'] = justificativa_match.group(1).strip()
        else: q['justificativa'] = None; logger.debug(f"Parser C/E Item Bloco {i+1}: Justificativa não encontrada.")

        questions.append(q)
        logger.debug(f"Parser C/E Item Bloco {i+1}: Item adicionado: {q}")

    if not questions and item_blocks: logger.error("Parser C/E: Nenhum item válido parseado dos blocos.")
    logger.info(f"Parser C/E (Motivador+Itens): Parsing finalizado. Motivador: {'Sim' if main_motivador else 'Não'}. Itens: {len(questions)}")

    return main_motivador, questions # Retorna a tupla
# ---------------------------------------------------------------------------
# FUNÇÃO 2: Parsing para Avaliação Discursiva (ESTRUTURA SIMPLIFICADA E CORRIGIDA)
# ---------------------------------------------------------------------------
def parse_evaluation_scores(text: str) -> dict:
    """
    Faz o parsing do texto bruto da avaliação discursiva da IA.
    Procura por marcadores comuns, sendo mais flexível com espaços e markdown.
    Retorna um dicionário com 'NC', 'NE', 'NPD', 'Justificativa_NC', 'Comentários'.
    Retorna None para valores numéricos se não puderem ser convertidos.
    """
    if not text:
        logger.warning("Parser Avaliação: Texto vazio.")
        return {'NC': None, 'NE': None, 'NPD': None, 'Justificativa_NC': None, 'Comentários': None}

    logger.info("Parser Avaliação: Iniciando parsing...")
    scores = {'NC': None, 'NE': None, 'NPD': None, 'Justificativa_NC': None, 'Comentários': None}

    # Define os padrões regex
    NC_PATTERN = r"\*?\*?NC:\*?\*?\s*([+-]?\d+(?:\.\d+)?)"
    NE_PATTERN = r"\*?\*?NE:\*?\*?\s*(\d+)"
    NPD_PATTERN = r"\*?\*?NPD:\*?\*?\s*([+-]?\d+(?:\.\d+)?)"
    JUST_NC_PATTERN = r"\*?\*?Justificativa NC:\*?\*?\s*(.*?)(?=\n\s*\*?\*?[\w\s()]+:\*?\*?|$)"
    COMM_PATTERN = r"\*?\*?Comentários?:\*?\*?\s*(.*?)(?=\n\s*\*?\*?[\w\s()]+:\*?\*?|$)"

    try:
        # --- NC ---
        nc_match = re.search(NC_PATTERN, text, re.IGNORECASE)
        if nc_match:
            try:
                scores['NC'] = float(nc_match.group(1))
                logger.info(f"Parser Avaliação: NC encontrado: {scores['NC']}")
            except (ValueError, TypeError, IndexError) as e:
                logger.warning(f"Parser Avaliação: Valor NC inválido ou erro no grupo. Match: '{nc_match.group(0)}'. Erro: {e}")
        else:
            logger.warning("Parser Avaliação: Padrão NC não encontrado.")

        # --- NE ---
        ne_match = re.search(NE_PATTERN, text, re.IGNORECASE)
        if ne_match:
            try:
                scores['NE'] = int(ne_match.group(1))
                logger.info(f"Parser Avaliação: NE encontrado: {scores['NE']}")
            except (ValueError, TypeError, IndexError) as e:
                 logger.warning(f"Parser Avaliação: Valor NE inválido ou erro no grupo. Match: '{ne_match.group(0)}'. Erro: {e}")
        else:
            logger.warning("Parser Avaliação: Padrão NE não encontrado.")

        # --- NPD ---
        npd_match = re.search(NPD_PATTERN, text, re.IGNORECASE)
        if npd_match:
             try:
                scores['NPD'] = float(npd_match.group(1))
                logger.info(f"Parser Avaliação: NPD encontrado: {scores['NPD']}")
             except (ValueError, TypeError, IndexError) as e:
                 logger.warning(f"Parser Avaliação: Valor NPD inválido ou erro no grupo. Match: '{npd_match.group(0)}'. Erro: {e}")
        else:
            logger.warning("Parser Avaliação: Padrão NPD não encontrado.")

        # --- Justificativa NC ---
        just_nc_match = re.search(JUST_NC_PATTERN, text, re.IGNORECASE | re.DOTALL)
        if just_nc_match:
            try:
                scores['Justificativa_NC'] = just_nc_match.group(1).strip()
                logger.info(f"Parser Avaliação: Justificativa NC encontrada ({len(scores['Justificativa_NC'])} chars).")
            except IndexError:
                 logger.warning(f"Parser Avaliação: Match 'Justificativa NC' encontrado, mas falha ao pegar grupo 1.")
        else:
            logger.warning("Parser Avaliação: Padrão 'Justificativa NC:' não encontrado.")

        # --- Comentários ---
        comm_match = re.search(COMM_PATTERN, text, re.IGNORECASE | re.DOTALL)
        if comm_match:
            try:
                scores['Comentários'] = comm_match.group(1).strip()
                logger.info(f"Parser Avaliação: Comentários encontrados ({len(scores['Comentários'])} chars).")
            except IndexError:
                logger.warning(f"Parser Avaliação: Match 'Comentários' encontrado, mas falha ao pegar grupo 1.")
        else:
            logger.warning("Parser Avaliação: Padrão Comentários não encontrado.")

    except Exception as e:
        logger.error(f"Erro inesperado durante o parsing da avaliação: {e}", exc_info=True)

    scores.setdefault('NC', None); scores.setdefault('NE', None); scores.setdefault('NPD', None)
    scores.setdefault('Justificativa_NC', None); scores.setdefault('Comentários', None)

    logger.info(f"Parser Avaliação: Parsing concluído. Resultado: {scores}")
    return scores
