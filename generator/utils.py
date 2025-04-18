# generator/utils.py (VERSÃO FINAL CORRIGIDA PARA AMBOS PARSERS)
import re
from .exceptions import ParsingError # Reutilizar a exceção de parsing
import logging

logger = logging.getLogger(__name__) # Logger específico para utils

# ---------------------------------------------------------------------------
# FUNÇÃO 1: Parsing para Questões Certo/Errado (Estratégia por Blocos)
# ---------------------------------------------------------------------------
def parse_ai_response_to_questions(text: str) -> list[dict]:
    """
    Faz o parsing do texto bruto da IA para extrair questões C/E estruturadas.
    Assume que itens são separados por '---' e cada bloco contém Afirmação, Gabarito, Justificativa.
    """
    if not text:
        logger.warning("Parser C/E: Texto vazio recebido.")
        return []

    logger.info("Parser C/E: Iniciando parsing (Estratégia por Blocos)...")
    questions = []
    # Divide o texto em blocos usando '---' como separador
    blocks = [block.strip() for block in re.split(r'\n---\n?', text.strip()) if block.strip()]

    if not blocks:
        logger.error("Parser C/E (Blocos): Nenhum bloco de questão encontrado após dividir por '---'.")
        return []

    logger.info(f"Parser C/E (Blocos): Encontrados {len(blocks)} blocos de texto.")

    for i, block in enumerate(blocks):
        logger.debug(f"Parser C/E (Blocos): Processando Bloco {i+1}...")
        q = {}
        # Regex para encontrar os campos DENTRO de cada bloco
        # Ajustado para capturar até o próximo marcador ou fim do bloco
        afirmacao_match = re.search(r"Afirmação:\s*(.*?)(?=\n(?:Gabarito:|Justificativa:)|$)", block, re.IGNORECASE | re.DOTALL)
        gabarito_match = re.search(r"\nGabarito:\s*(C|E)\b", block, re.IGNORECASE) # Procura em nova linha
        justificativa_match = re.search(r"\nJustificativa:\s*(.*)", block, re.IGNORECASE | re.DOTALL) # Procura em nova linha

        if afirmacao_match: q['afirmacao'] = afirmacao_match.group(1).strip()
        else: logger.warning(f"Parser C/E Bloco {i+1}: 'Afirmação:' não encontrada."); continue

        if gabarito_match: q['gabarito'] = gabarito_match.group(1).strip().upper()
        else: logger.warning(f"Parser C/E Bloco {i+1}: 'Gabarito:' não encontrado."); continue

        if justificativa_match: q['justificativa'] = justificativa_match.group(1).strip(); logger.debug(f"Parser C/E Bloco {i+1}: Justificativa encontrada.")
        else: q['justificativa'] = None; logger.debug(f"Parser C/E Bloco {i+1}: Justificativa não encontrada.")

        questions.append(q)
        logger.debug(f"Parser C/E Bloco {i+1}: Item adicionado: {q}")

    if not questions and blocks: logger.error("Parser C/E (Blocos): Nenhum bloco parseado com sucesso."); return []
    elif not questions: logger.warning("Parser C/E (Blocos): Nenhuma questão extraída."); return []

    logger.info(f"Parser C/E: Parsing (Blocos) finalizado. Questões válidas: {len(questions)}")
    return questions


# ---------------------------------------------------------------------------
# FUNÇÃO 2: Parsing para Avaliação Discursiva (ATUALIZADA)
# ---------------------------------------------------------------------------
def parse_evaluation_scores(text: str) -> dict:
    """
    Faz o parsing do texto bruto da avaliação discursiva da IA.
    Procura por marcadores como **NC:**, **NE:**, **NPD:**, **Justificativa NC:**, **Comentários:**.
    """
    if not text: logger.warning("Parser Avaliação: Texto vazio."); return {'NC': None, 'NE': None, 'NPD': None, 'Justificativa_NC': None, 'Comentários': None}

    logger.info("Parser Avaliação: Iniciando parsing...");
    # Chave 'Justificativa_NC' para o novo campo do prompt rígido
    scores = {'NC': None, 'NE': None, 'NPD': None, 'Justificativa_NC': None, 'Comentários': None}

    try:
        # --- NC (Float/Int) ---
        nc_match = re.search(r"\*?\*?NC:\*?\*?\s*([+-]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if nc_match:
            try: scores['NC'] = float(nc_match.group(1)); logger.info(f"Parser Avaliação: NC: {scores['NC']}")
            except (ValueError, TypeError): logger.warning(f"Parser Avaliação: Valor NC ('{nc_match.group(1)}') inválido."); scores['NC'] = "Erro Parse"
        else: logger.warning("Parser Avaliação: Padrão NC não encontrado.")

        # --- NE (Inteiro) ---
        ne_match = re.search(r"\*?\*?NE:\*?\*?\s*(\d+)", text, re.IGNORECASE)
        if ne_match:
            try: scores['NE'] = int(ne_match.group(1)); logger.info(f"Parser Avaliação: NE: {scores['NE']}")
            except (ValueError, TypeError): logger.warning(f"Parser Avaliação: Valor NE ('{ne_match.group(1)}') inválido."); scores['NE'] = "Erro Parse"
        else: logger.warning("Parser Avaliação: Padrão NE não encontrado.")

        # --- NPD (Float/Int) ---
        npd_match = re.search(r"\*?\*?NPD:\*?\*?\s*([+-]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if npd_match:
             try: scores['NPD'] = float(npd_match.group(1)); logger.info(f"Parser Avaliação: NPD: {scores['NPD']}")
             except (ValueError, TypeError): logger.warning(f"Parser Avaliação: Valor NPD ('{npd_match.group(1)}') inválido."); scores['NPD'] = "Erro Parse"
        else: logger.warning("Parser Avaliação: Padrão NPD não encontrado.")

        # --- Justificativa NC (Texto multilinha - NOVO CAMPO) ---
        # Procura por '**Justificativa NC:**' e captura tudo até a próxima linha que começa com '**' (outro marcador) ou fim do texto
        just_nc_match = re.search(r"\*?\*?Justificativa NC:\*?\*?\s*(.*?)(?=\n\s*\*\*|\Z)", text, re.IGNORECASE | re.DOTALL)
        if just_nc_match:
            scores['Justificativa_NC'] = just_nc_match.group(1).strip()
            logger.info(f"Parser Avaliação: Justificativa NC encontrada: {scores['Justificativa_NC'][:100]}...")
        else:
            logger.warning("Parser Avaliação: Padrão 'Justificativa NC:' não encontrado.")
            scores['Justificativa_NC'] = None

        # --- Comentários (Texto multilinha) ---
        # Procura por '**Comentários:**' e captura tudo até a próxima linha que começa com '**' (outro marcador) ou fim do texto
        comm_match = re.search(r"\*?\*?Comentários?:\*?\*?\s*(.*?)(?=\n\s*\*\*|\Z)", text, re.IGNORECASE | re.DOTALL)
        if comm_match:
            scores['Comentários'] = comm_match.group(1).strip()
            logger.info(f"Parser Avaliação: Comentários encontrados: {scores['Comentários'][:100]}...")
        else:
            logger.warning("Parser Avaliação: Padrão Comentários não encontrado.")
            scores['Comentários'] = None

    except Exception as e:
        logger.error(f"Erro inesperado no parser da avaliação: {e}", exc_info=True)
        # Pode adicionar o erro a um campo ou retornar dicionário como está
        if scores['Comentários'] is None: scores['Comentários'] = f"Erro interno no parser: {e}"
        else: scores['Comentários'] += f"\n[Erro interno no parser: {e}]"


    # Garante chaves (redundante se inicializado com None, mas seguro)
    scores.setdefault('NC', None); scores.setdefault('NE', None); scores.setdefault('NPD', None)
    scores.setdefault('Justificativa_NC', None); scores.setdefault('Comentários', None)

    logger.info(f"Parser Avaliação: Parsing concluído. Resultado: {scores}")
    return scores