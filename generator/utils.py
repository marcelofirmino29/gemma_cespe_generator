# generator/utils.py
import re
from .exceptions import ParsingError
import logging

logger = logging.getLogger(__name__)

def parse_ai_response_to_questions(text: str) -> tuple[str | None, list[dict]]:
    """
    Faz o parsing do texto C/E no formato: 1 Motivador Principal + N Itens.
    Versão robusta que ignora numerações automáticas da IA (ex: Item 1, Item 2).
    """
    if not text: 
        logger.warning("Parser C/E: Texto vazio.")
        return None, []
        
    main_motivador = None
    questions = []
    text_cleaned = text.strip()

    # 1. Extração do Motivador (mais flexível com espaços e asteriscos)
    motivador_regex = r"(?i)\*?\*?Texto Motivador(?: Principal)?:\*?\*?\s*(.*?)(?=\n\s*\*?\*?Item(?:\s*\d+)?:\*?\*?|\n\s*---|$)"
    motivador_match = re.search(motivador_regex, text_cleaned, re.DOTALL)
    remaining_text = text_cleaned

    if motivador_match:
        motivador_text = motivador_match.group(1).strip()
        if motivador_text.lower() != 'não aplicável':
            main_motivador = motivador_text
        remaining_text = text_cleaned[motivador_match.end():].strip()

    # 2. Processa blocos de Itens (divididos por ---)
    item_blocks = [block.strip() for block in re.split(r'\s*---\s*', remaining_text) if block.strip()]

    for i, block in enumerate(item_blocks):
        q = {}
        # REGEX AJUSTADA: Agora aceita "Item:", "Item 1:", "**Item 1:**", "Afirmação 1:", etc.
        item_match = re.search(r"(?i)\*?\*?(?:Item|Afirmação)(?:\s*\d+)?:\*?\*?\s*(.*?)(?=\n\s*\*?\*?Gabarito:\*?\*?|$)", block, re.DOTALL)
        gabarito_match = re.search(r"(?i)\*?\*?Gabarito:\*?\*?\s*(C|E)\b", block)
        justificativa_match = re.search(r"(?i)\*?\*?Justificativa:\*?\*?\s*(.*)", block, re.DOTALL)

        if item_match and gabarito_match:
            # Remove asteriscos residuais da afirmação para não sujar o banco de dados
            afirmacao_limpa = item_match.group(1).strip().replace('**', '')
            
            q['afirmacao'] = afirmacao_limpa
            q['gabarito'] = gabarito_match.group(1).strip().upper()
            q['justificativa'] = justificativa_match.group(1).strip() if justificativa_match else None
            questions.append(q)

    return main_motivador, questions

def parse_discursive_question(text: str) -> dict:
    """
    Separa Contexto, Comando e Alíneas evitando confusão com siglas (TIC, MGI).
    """
    if not text: return {"contexto": "", "comando": "", "alineas": []}
    text = text.replace('\r\n', '\n').strip()
    data = {"contexto": "", "comando": "", "alineas": []}

    # Contexto
    context_match = re.search(r"(?i)(?:#+\s*)?Contexto[:\s]*(.*?)(?=(?:#+\s*)?Comando|$)", text, re.DOTALL)
    if context_match: data["contexto"] = context_match.group(1).strip()

    # Comando
    comando_match = re.search(r"(?i)(?:#+\s*)?Comando[:\s]*(.*?)(?=\n\s*[a-z]\)\s+|$)", text, re.DOTALL)
    if comando_match: data["comando"] = comando_match.group(1).strip()

    # Alíneas (Exige início de linha ^ e espaço após o parêntese)
    items = re.findall(r"^\s*([a-z]\))\s+(.*?)(?=\n\s*[a-z]\)\s+|$)", text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    for label, content in items:
        data["alineas"].append({"id": label.lower(), "texto": content.strip()})

    return data

def parse_evaluation_scores(text: str) -> dict:
    """
    Parsing do feedback da avaliação discursiva.
    """
    if not text:
        return {'NC': None, 'NE': None, 'NPD': None, 'Justificativa_NC': None, 'Comentários': None}

    scores = {'NC': None, 'NE': None, 'NPD': None, 'Justificativa_NC': None, 'Comentários': None}
    
    # Captura valores numéricos
    for key, pat in {'NC': r"NC:\s*([\d.]+)", 'NE': r"NE:\s*(\d+)", 'NPD': r"NPD:\s*([\d.]+)"}.items():
        m = re.search(pat, text, re.IGNORECASE)
        if m: scores[key] = m.group(1)

    # Captura Justificativa e Comentários
    just_match = re.search(r"(?i)Justificativa NC:\s*(.*?)(?=\n\s*(?:Comentários|NC|NE|NPD):|$)", text, re.DOTALL)
    comm_match = re.search(r"(?i)Comentários?:\s*(.*?)(?=\n\s*(?:Justificativa|NC|NE|NPD):|$)", text, re.DOTALL)

    scores['Justificativa_NC'] = just_match.group(1).strip() if just_match else None
    if comm_match:
        scores['Comentários'] = comm_match.group(1).strip()
    else:
        scores['Comentários'] = text.split("Justificativa NC:")[0].strip()

    return scores

STOP_WORDS_PT = set([
    'a', 'à', 'agora', 'ainda', 'além', 'algo', 'alguém', 'algum', 'alguma', 'algumas', 'alguns', 'ali',
    'ampla', 'amplas', 'amplo', 'amplos', 'ano', 'anos', 'ante', 'antes', 'ao', 'aos', 'apenas', 'apoio', 'após',
    'as', 'às', 'assim', 'até', 'atrás', 'através', 'baixo', 'bastante', 'bem', 'boa', 'boas', 'bom', 'bons',
    'cada', 'cento', 'certamente', 'certeza', 'cima', 'cinco', 'com', 'como', 'contra', 'contudo', 'da', 'dá',
    'dar', 'das', 'de', 'dela', 'delas', 'dele', 'deles', 'demais', 'dentro', 'depois', 'desde', 'dessa', 'dessas',
    'deve', 'devem', 'dever', 'deverá', 'deverão', 'deveria', 'devia', 'dia', 'diante', 'disse', 'disso', 'do',
    'dois', 'dos', 'duas', 'e', 'é', 'ela', 'elas', 'ele', 'eles', 'em', 'embora', 'enquanto', 'entre', 'era', 'eram',
    'essa', 'essas', 'esse', 'esses', 'esta', 'está', 'estamos', 'estão', 'estar', 'estas', 'este', 'esteja', 'estejam',
    'estes', 'esteve', 'estive', 'estou', 'eu', 'exemplo', 'faz', 'fazem', 'fazer', 'fez', 'fim', 'final', 'foi', 'fomos',
    'for', 'fora', 'foram', 'forem', 'formos', 'fosse', 'foste', 'fui', 'geral', 'grande', 'há', 'haja', 'hajam', 'houve',
    'isso', 'isto', 'já', 'lá', 'lhe', 'lhes', 'lo', 'local', 'logo', 'longe', 'lugar', 'maior', 'mais', 'mas', 'me', 'meio',
    'menos', 'mesma', 'mesmas', 'mesmo', 'mesmos', 'meu', 'meus', 'minha', 'minhas', 'muito', 'na', 'nada', 'não', 'nas',
    'nem', 'nenhum', 'nessa', 'nesta', 'neste', 'no', 'nos', 'nós', 'nossa', 'nosso', 'nossos', 'nova', 'novo', 'num',
    'numa', 'número', 'nunca', 'o', 'os', 'ou', 'outra', 'outro', 'para', 'parece', 'parte', 'pela', 'pelas', 'pelo',
    'pelos', 'pode', 'podem', 'poder', 'pois', 'ponto', 'pontos', 'por', 'porém', 'porque', 'posso', 'pouco', 'primeiro',
    'próprio', 'próximo', 'quais', 'qual', 'quando', 'quanto', 'que', 'quê', 'quem', 'quer', 'relação', 'sabe', 'são',
    'se', 'segundo', 'sei', 'seis', 'seja', 'sejam', 'sem', 'sempre', 'sendo', 'ser', 'será', 'serão', 'seria', 'seu',
    'seus', 'si', 'sido', 'sim', 'sistema', 'só', 'sob', 'sobre', 'somos', 'sou', 'sua', 'suas', 'tal', 'talvez',
    'também', 'tanto', 'tão', 'tarde', 'te', 'tem', 'tém', 'têm', 'tenha', 'tenho', 'ter', 'terá', 'terão', 'teu',
    'teus', 'teve', 'ti', 'tido', 'tinha', 'tínhamos', 'tive', 'tivemos', 'toda', 'todas', 'todo', 'todos', 'três',
    'tu', 'tua', 'tudo', 'um', 'uma', 'umas', 'uns', 'vai', 'vão', 'vários', 'vem', 'vêm', 'ver', 'vez', 'vezes',
    'vindo', 'você', 'vocês', 'vos', 'vós', 'zero', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0'
])