# generator/utils.py
import re
from .exceptions import ParsingError # Reutilizar a exceção de parsing
import logging

# Configura um logger para este módulo (ou use o logger do app 'generator')
logger = logging.getLogger(__name__) # Usar __name__ é uma boa prática para loggers de módulo

# ---------------------------------------------------------------------------
# FUNÇÃO 1: Parsing para Questões Certo/Errado (Função que você já tinha)
# ---------------------------------------------------------------------------
def parse_ai_response_to_questions(text: str) -> list[dict]:
    """
    Faz o parsing do texto bruto da IA para extrair questões C/E estruturadas.
    Formato esperado: blocos --- QUESTÃO --- ... --- FIM --- ou linhas Afirmação:/Resposta:/Justificativa:.
    Lança ParsingError se o formato essencial não for encontrado.

    Retorna:
        Uma lista de dicionários [{afirmacao, resposta, justificativa}, ...].
    """
    questions = []
    # Regex para blocos principais
    question_blocks = re.findall(r"--- QUESTÃO ---\s*(.*?)\s*--- FIM ---", text, re.DOTALL | re.IGNORECASE)

    if question_blocks:
        # Processamento principal se o regex de blocos funcionou
        logger.info(f"Parser C/E: Encontrados {len(question_blocks)} blocos via regex principal.")
        for i, block in enumerate(question_blocks):
            q = {}
            afirmacao_match = re.search(r"Afirmação:(.*?)(?:Resposta:|Justificativa:|$)", block, re.DOTALL | re.IGNORECASE)
            resposta_match = re.search(r"Resposta:(.*?)(?:Justificativa:|$)", block, re.DOTALL | re.IGNORECASE)
            justificativa_match = re.search(r"Justificativa:(.*)", block, re.DOTALL | re.IGNORECASE)

            if afirmacao_match: q['afirmacao'] = afirmacao_match.group(1).strip()
            else: logger.warning(f"Parser C/E: Bloco {i+1}, 'Afirmação:' não encontrada."); continue

            if resposta_match: q['resposta'] = resposta_match.group(1).strip().upper()
            else: logger.warning(f"Parser C/E: Bloco {i+1}, 'Resposta:' não encontrada."); continue # Resposta é essencial

            # Validar resposta C/E
            if q['resposta'] not in ['C', 'E']:
                 logger.warning(f"Parser C/E: Bloco {i+1}, Resposta inválida ('{q['resposta']}'). Pulando item.")
                 continue

            if justificativa_match: q['justificativa'] = justificativa_match.group(1).strip()
            else: q['justificativa'] = "Não fornecida."

            questions.append(q)

        if not questions: # Tinha blocos, mas nenhum parseado com sucesso
            logger.error("Parser C/E: Blocos encontrados, mas falha ao parsear Afirmação/Resposta.")
            raise ParsingError("Blocos de questão C/E encontrados, mas falha ao parsear campos internos.")

    else:
        # Tentar fallback por linhas se o formato principal falhar
        logger.warning("Parser C/E: Formato '--- QUESTÃO ---' não encontrado. Tentando fallback por linhas.")
        lines = text.strip().split('\n')
        current_q = {}
        for line in lines:
            line = line.strip()
            if not line: continue # Ignora linhas vazias

            if line.lower().startswith("afirmação:"):
                if current_q.get('afirmacao') and current_q.get('resposta'): # Salva anterior se completo
                     current_q.setdefault('justificativa', "Não fornecida.")
                     questions.append(current_q)
                current_q = {'afirmacao': re.sub(r"^afirmação:", "", line, flags=re.IGNORECASE).strip()}
            elif line.lower().startswith("resposta:") and 'afirmacao' in current_q:
                resposta_val = re.sub(r"^resposta:", "", line, flags=re.IGNORECASE).strip().upper()
                if resposta_val in ['C', 'E']:
                    current_q['resposta'] = resposta_val
                else:
                    logger.warning(f"Parser C/E (Fallback): Resposta inválida ('{resposta_val}'). Ignorando item.")
                    current_q = {} # Descarta item inválido
            elif line.lower().startswith("justificativa:") and 'afirmacao' in current_q:
                 current_q['justificativa'] = re.sub(r"^justificativa:", "", line, flags=re.IGNORECASE).strip()
            elif 'afirmacao' in current_q and 'resposta' not in current_q:
                 # Assume continuação da afirmação se ainda não achou resposta
                 current_q['afirmacao'] += " " + line
            elif 'resposta' in current_q and 'justificativa' not in current_q:
                  # Assume continuação da justificativa se já tem resposta
                  current_q.setdefault('justificativa', "") # Inicializa se não existe
                  current_q['justificativa'] += " " + line

        if current_q.get('afirmacao') and current_q.get('resposta'): # Salva a última questão
            current_q.setdefault('justificativa', "Não fornecida.")
            questions.append(current_q)

        if not questions: # Se nem o fallback funcionou
            logger.error(f"Parser C/E: Falha total no parsing. Texto (início): {text[:500]}...")
            raise ParsingError("Não foi possível encontrar ou parsear questões C/E na resposta da IA.")

        logger.info(f"Parser C/E: Parsing via fallback. Questões: {len(questions)}")

    logger.info(f"Parser C/E: Parsing finalizado. Questões extraídas: {len(questions)}")
    return questions


# ---------------------------------------------------------------------------
# FUNÇÃO 2: Parsing para Avaliação Discursiva (Função que faltava)
# ---------------------------------------------------------------------------
def parse_evaluation_scores(text: str) -> dict:
    """
    Faz o parsing do texto bruto da avaliação discursiva da IA.
    Procura por marcadores como **NC:**, **NE:**, **NPD:**, **Justificativa:**, **Comentários:**.

    Args:
        text: O texto bruto retornado pela API Generative AI na avaliação.

    Returns:
        Um dicionário com as chaves 'NC', 'NE', 'NPD', 'Justificativa', 'Comentários'.
        Valores podem ser float, int, string ou None se não encontrados/parseados.
    """
    if not text:
        logger.warning("Parser Avaliação: Texto para parsing está vazio.")
        return {'NC': None, 'NE': None, 'NPD': None, 'Justificativa': None, 'Comentários': None}

    logger.info("Parser Avaliação: Iniciando parsing do resultado...")
    scores = {'NC': None, 'NE': None, 'NPD': None, 'Justificativa': None, 'Comentários': None}

    try:
        # Regex para NC (Float/Int) - Busca número após o marcador, ignorando texto extra
        nc_match = re.search(r"\*?\*?NC:\*?\*?\s*([+-]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if nc_match:
            try:
                scores['NC'] = float(nc_match.group(1))
                logger.info(f"Parser Avaliação: NC encontrado: {scores['NC']}")
            except (ValueError, TypeError):
                logger.warning(f"Parser Avaliação: Valor NC encontrado ('{nc_match.group(1)}') mas não é float válido.")
                scores['NC'] = "Erro Parse"
        else:
            logger.warning("Parser Avaliação: Padrão para NC não encontrado.")

        # Regex para NE (Inteiro) - Busca número após o marcador, ignorando texto extra
        ne_match = re.search(r"\*?\*?NE:\*?\*?\s*(\d+)", text, re.IGNORECASE)
        if ne_match:
            try:
                scores['NE'] = int(ne_match.group(1))
                logger.info(f"Parser Avaliação: NE encontrado: {scores['NE']}")
            except (ValueError, TypeError):
                logger.warning(f"Parser Avaliação: Valor NE encontrado ('{ne_match.group(1)}') mas não é int válido.")
                scores['NE'] = "Erro Parse"
        else:
            logger.warning("Parser Avaliação: Padrão para NE não encontrado.")

        # Regex para NPD (Float/Int) - Busca número após o marcador, ignorando texto extra
        npd_match = re.search(r"\*?\*?NPD:\*?\*?\s*([+-]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if npd_match:
            try:
                scores['NPD'] = float(npd_match.group(1))
                logger.info(f"Parser Avaliação: NPD encontrado: {scores['NPD']}")
            except (ValueError, TypeError):
                logger.warning(f"Parser Avaliação: Valor NPD encontrado ('{npd_match.group(1)}') mas não é float válido.")
                scores['NPD'] = "Erro Parse"
        else:
            logger.warning("Parser Avaliação: Padrão para NPD não encontrado.")

        # Regex para Justificativa (Texto multilinha)
        # Captura texto após '**Justificativa:**' até a próxima linha que começa com '**' ou o fim do texto
        just_match = re.search(r"\*?\*?Justificativa:\*?\*?\s*(.*?)(?=\n\s*\*\*|\Z)", text, re.IGNORECASE | re.DOTALL)
        if just_match:
            scores['Justificativa'] = just_match.group(1).strip()
            logger.info(f"Parser Avaliação: Justificativa encontrada: {scores['Justificativa'][:100]}...")
        else:
            logger.warning("Parser Avaliação: Padrão para Justificativa não encontrado.")
            scores['Justificativa'] = None

        # Regex para Comentários (Texto multilinha)
        comm_match = re.search(r"\*?\*?Comentários?:\*?\*?\s*(.*?)(?=\n\s*\*\*|\Z)", text, re.IGNORECASE | re.DOTALL)
        if comm_match:
            scores['Comentários'] = comm_match.group(1).strip()
            logger.info(f"Parser Avaliação: Comentários encontrados: {scores['Comentários'][:100]}...")
        else:
            logger.warning("Parser Avaliação: Padrão para Comentários não encontrado.")
            scores['Comentários'] = None

        # Se não achou Comentários mas achou Justificativa, talvez copiar? Ou deixar separado?
        # Decisão: Deixar separado por enquanto. O template decide o que mostrar.
        if scores['Comentários'] is None and scores['Justificativa'] is not None:
            logger.info("Parser Avaliação: Comentários não encontrados, mas Justificativa sim.")
            # Não copia automaticamente para 'Comentários', mantém separado.

    except Exception as e:
        logger.error(f"Erro inesperado no parser da avaliação: {e}", exc_info=True)
        # Retorna o dicionário com o que conseguiu parsear + um erro geral
        scores['Comentários'] = f"Erro interno no parser da avaliação: {e}"

    # Garante que as chaves principais existam com None se não foram achadas
    scores.setdefault('NC', None)
    scores.setdefault('NE', None)
    scores.setdefault('NPD', None)
    scores.setdefault('Justificativa', None)
    scores.setdefault('Comentários', None) # Define None se não achou

    logger.info(f"Parser Avaliação: Parsing concluído. Resultado: {scores}")
    return scores