# generator/utils.py
import re
from .exceptions import ParsingError
import logging # Usar logging

logger = logging.getLogger(__name__)

def parse_ai_response_to_questions(text: str) -> list[dict]:
    """
    Faz o parsing do texto bruto da IA para extrair as questões estruturadas.
    Lança ParsingError se o formato essencial não for encontrado.

    Retorna:
        Uma lista de dicionários, onde cada dicionário representa uma questão
        com chaves 'afirmacao', 'resposta', e 'justificativa'.
    """
    questions = []
    # Regex mais robusto para capturar os blocos
    # Procura por --- QUESTÃO ---, captura tudo até --- FIM --- (não-guloso)
    question_blocks = re.findall(r"--- QUESTÃO ---\s*(.*?)\s*--- FIM ---", text, re.DOTALL | re.IGNORECASE)

    if not question_blocks:
        # Tentar fallback se o formato principal falhar (adaptado da versão anterior)
        logger.warning("Formato principal '--- QUESTÃO --- ... --- FIM ---' não encontrado. Tentando fallback por linhas.")
        lines = text.strip().split('\n')
        current_q = {}
        for line in lines:
            line = line.strip()
            if line.lower().startswith("afirmação:"):
                if current_q and 'afirmacao' in current_q and 'resposta' in current_q:
                    if 'justificativa' not in current_q: current_q['justificativa'] = "Não fornecida."
                    questions.append(current_q)
                current_q = {'afirmacao': re.sub(r"afirmação:", "", line, flags=re.IGNORECASE).strip()}
            elif line.lower().startswith("resposta:"):
                 # Verifica se a afirmação já foi adicionada para evitar respostas órfãs
                if 'afirmacao' in current_q:
                    current_q['resposta'] = re.sub(r"resposta:", "", line, flags=re.IGNORECASE).strip()
                else:
                    logger.warning(f"Encontrada 'Resposta:' sem 'Afirmação:' precedente: {line}")
            elif line.lower().startswith("justificativa:"):
                 if 'afirmacao' in current_q: # Só adiciona se pertence a uma questão
                    current_q['justificativa'] = re.sub(r"justificativa:", "", line, flags=re.IGNORECASE).strip()
                 else:
                     logger.warning(f"Encontrada 'Justificativa:' sem 'Afirmação:' precedente: {line}")


        if current_q and 'afirmacao' in current_q and 'resposta' in current_q: # Salva a última questão
            if 'justificativa' not in current_q: current_q['justificativa'] = "Não fornecida."
            questions.append(current_q)

        if not questions: # Se nem o fallback funcionou
            logger.error(f"Falha no parsing (fallback). Nenhuma questão encontrada. Texto recebido (início): {text[:500]}...")
            raise ParsingError("Não foi possível encontrar ou parsear blocos de questões na resposta da IA (mesmo com fallback).")

        logger.info(f"Parsing realizado via fallback. Questões encontradas: {len(questions)}")
        return questions

    # Processamento principal se o regex funcionou
    logger.info(f"Encontrados {len(question_blocks)} blocos de questão via regex principal.")
    for i, block in enumerate(question_blocks):
        q = {}
        # Regex dentro do bloco para extrair os campos
        afirmacao_match = re.search(r"Afirmação:(.*?)(?:Resposta:|Justificativa:|$)", block, re.DOTALL | re.IGNORECASE)
        resposta_match = re.search(r"Resposta:(.*?)(?:Justificativa:|$)", block, re.DOTALL | re.IGNORECASE)
        justificativa_match = re.search(r"Justificativa:(.*)", block, re.DOTALL | re.IGNORECASE)

        if afirmacao_match:
            q['afirmacao'] = afirmacao_match.group(1).strip()
        else:
            logger.warning(f"Bloco {i+1} detectado por regex, mas 'Afirmação:' não encontrada dentro dele.")
            continue # Pula para o próximo bloco

        if resposta_match:
            q['resposta'] = resposta_match.group(1).strip()
        else:
            logger.warning(f"Bloco {i+1} detectado (Afirmação: '{q['afirmacao'][:50]}...'), mas 'Resposta:' não encontrada.")
            continue # Pula para o próximo bloco, Resposta é essencial

        if justificativa_match:
            q['justificativa'] = justificativa_match.group(1).strip()
        else:
            q['justificativa'] = "Não fornecida." # Padrão se não encontrada

        questions.append(q)

    if not questions and question_blocks: # Tinha blocos, mas nenhum foi parseado com sucesso
        logger.error("Blocos de questão foram encontrados via regex, mas não foi possível parsear Afirmação/Resposta de nenhum deles.")
        raise ParsingError("Blocos de questão foram encontrados, mas não foi possível parsear os campos internos (Afirmação/Resposta).")
    elif not questions: # Nenhuma questão por nenhum método (caso raro aqui devido ao raise anterior)
         logger.error("Nenhuma questão encontrada após todos os métodos de parsing.")
         raise ParsingError("Nenhuma questão pode ser extraída da resposta da IA.")


    logger.info(f"Parsing realizado via regex principal. Questões extraídas com sucesso: {len(questions)}")
    return questions