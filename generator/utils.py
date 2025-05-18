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

# --- Lista de Stop Words (Português) ---
# (Pode ser expandida ou movida para um arquivo/setting separado)
STOP_WORDS_PT = set([
    'a', 'à', 'adeus', 'agora', 'aí', 'ainda', 'além', 'algo', 'alguém', 'algum', 'alguma', 'algumas', 'alguns', 'ali',
    'ampla', 'amplas', 'amplo', 'amplos', 'ano', 'anos', 'ante', 'antes', 'ao', 'aos', 'apenas', 'apoio', 'após', 'aquela',
    'aquelas', 'aquele', 'aqueles', 'aqui', 'aquilo', 'área', 'as', 'às', 'assim', 'até', 'atrás', 'através', 'baixo',
    'bastante', 'bem', 'boa', 'boas', 'bom', 'bons', 'breve', 'cá', 'cada', 'catorze', 'cedo', 'cento', 'certamente',
    'certeza', 'cima', 'cinco', 'coisa', 'coisas', 'com', 'como', 'conselho', 'contra', 'contudo', 'custa', 'da', 'dá',
    'dão', 'daquela', 'daquelas', 'daquele', 'daqueles', 'dar', 'das', 'de', 'debaixo', 'dela', 'delas', 'dele', 'deles',
    'demais', 'dentro', 'depois', 'desde', 'dessa', 'dessas', 'desse', 'desses', 'desta', 'destas', 'deste', 'destes',
    'deve', 'devem', 'devendo', 'dever', 'deverá', 'deverão', 'deveria', 'deveriam', 'devia', 'deviam', 'dez', 'dezanove',
    'dezasseis', 'dezassete', 'dezoito', 'dia', 'diante', 'disse', 'disso', 'disto', 'dito', 'diz', 'dizem', 'dizer', 'do',
    'dois', 'dos', 'doze', 'duas', 'dúvida', 'e', 'é', 'ela', 'elas', 'ele', 'eles', 'em', 'embora', 'enquanto', 'entre',
    'era', 'eram', 'éramos', 'és', 'essa', 'essas', 'esse', 'esses', 'esta', 'está', 'estamos', 'estão', 'estar', 'estas',
    'estás', 'estava', 'estavam', 'estávamos', 'este', 'esteja', 'estejam', 'estejamos', 'estes', 'esteve', 'estive',
    'estivemos', 'estiver', 'estivera', 'estiveram', 'estivéramos', 'estiverem', 'estivermos', 'estivesse', 'estivessem',
    'estivéssemos', 'estiveste', 'estivestes', 'estou', 'etc', 'eu', 'exemplo', 'faço', 'falta', 'favor', 'faz', 'fazeis',
    'fazem', 'fazemos', 'fazer', 'fazes', 'fazia', 'façamos', 'fez', 'fim', 'final', 'foi', 'fomos', 'for', 'fora', 'foram',
    'fôramos', 'forem', 'formos', 'fosse', 'fossem', 'fôssemos', 'foste', 'fostes', 'fui', 'geral', 'grande', 'grandes',
    'grupo', 'há', 'haja', 'hajam', 'hajamos', 'havemos', 'havia', 'hei', 'hoje', 'hora', 'horas', 'houve', 'houvemos',
    'houver', 'houvera', 'houverá', 'houveram', 'houvéramos', 'houverão', 'houverei', 'houverem', 'houveremos', 'houveria',
    'houveriam', 'houveríamos', 'houvermos', 'houvesse', 'houvessem', 'houvéssemos', 'isso', 'isto', 'já', 'la', 'lá',
    'lado', 'lhe', 'lhes', 'lo', 'local', 'logo', 'longe', 'lugar', 'maior', 'maioria', 'mais', 'mal', 'mas', 'máximo',
    'me', 'meio', 'menor', 'menos', 'mês', 'meses', 'mesma', 'mesmas', 'mesmo', 'mesmos', 'meu', 'meus', 'mil', 'minha',
    'minhas', 'momento', 'muita', 'muitas', 'muito', 'muitos', 'na', 'nada', 'não', 'naquela', 'naquelas', 'naquele',
    'naqueles', 'nas', 'nem', 'nenhum', 'nenhuma', 'nessa', 'nessas', 'nesse', 'nesses', 'nesta', 'nestas', 'neste',
    'nestes', 'ninguém', 'nível', 'no', 'noite', 'nome', 'nos', 'nós', 'nossa', 'nossas', 'nosso', 'nossos', 'nova',
    'novas', 'nove', 'novo', 'novos', 'num', 'numa', 'número', 'nunca', 'o', 'obra', 'obrigada', 'obrigado', 'oitava',
    'oitavo', 'oito', 'onde', 'ontem', 'onze', 'os', 'ou', 'outra', 'outras', 'outro', 'outros', 'para', 'parece', 'parte',
    'partir', 'paucas', 'pela', 'pelas', 'pelo', 'pelos', 'pequena', 'pequenas', 'pequeno', 'pequenos', 'per', 'perante',
    'perto', 'pode', 'pude', 'pôde', 'podem', 'podendo', 'poder', 'poderia', 'poderiam', 'podia', 'podiam', 'põe', 'põem',
    'pois', 'ponto', 'pontos', 'por', 'porém', 'porque', 'porquê', 'posição', 'possível', 'possivelmente', 'posso', 'pouca',
    'poucas', 'pouco', 'poucos', 'primeira', 'primeiras', 'primeiro', 'primeiros', 'própria', 'próprias', 'próprio',
    'próprios', 'próxima', 'próximas', 'próximo', 'próximos', 'pude', 'puderam', 'quais', 'quáis', 'qual', 'quando',
    'quanto', 'quantos', 'quarta', 'quarto', 'quatro', 'que', 'quê', 'quem', 'quer', 'quereis', 'querem', 'queremas',
    'queres', 'quero', 'questão', 'quinta', 'quinto', 'quinze', 'relação', 'sabe', 'sabem', 'são', 'se', 'segunda',
    'segundo', 'sei', 'seis', 'seja', 'sejam', 'sejamos', 'sem', 'sempre', 'sendo', 'ser', 'será', 'serão', 'serei',
    'seremos', 'seria', 'seriam', 'seríamos', 'sete', 'sétima', 'sétimo', 'seu', 'seus', 'si', 'sido', 'sim', 'sistema',
    'só', 'sob', 'sobre', 'sois', 'somos', 'sou', 'sua', 'suas', 'tal', 'talvez', 'também', 'tampouco', 'tanta', 'tantas',
    'tanto', 'tão', 'tarde', 'te', 'tem', 'tém', 'têm', 'temos', 'tendes', 'tendo', 'tenha', 'tenham', 'tenhamos', 'tenho',
    'tens', 'ter', 'terá', 'terão', 'terceira', 'terceiro', 'terei', 'teremos', 'teria', 'teriam', 'teríamos', 'teu',
    'teus', 'teve', 'ti', 'tido', 'tinha', 'tinham', 'tínhamos', 'tive', 'tivemos', 'tiver', 'tivera', 'tiveram',
    'tivéramos', 'tiverem', 'tivermos', 'tivesse', 'tivessem', 'tivéssemos', 'tiveste', 'tivestes', 'toda', 'todas',
    'todavia', 'todo', 'todos', 'trabalho', 'três', 'treze', 'tu', 'tua', 'tuas', 'tudo', 'última', 'últimas', 'último',
    'últimos', 'um', 'uma', 'umas', 'uns', 'vai', 'vais', 'vão', 'vários', 'vem', 'vêm', 'vendo', 'ver', 'vez', 'vezes',
    'viagem', 'vindo', 'vinte', 'vir', 'você', 'vocês', 'vos', 'vós', 'vossa', 'vossas', 'vosso', 'vossos', 'zero', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '_'
    # Adicionar palavras específicas do domínio que não agregam valor (ex: 'questão', 'item', 'certo', 'errado', 'julgue')
    'afirmativa', 'abaixo', 'acerca', 'acima', 'apresentado', 'aspecto', 'assertiva', 'assinale', 'comando', 'conforme',
    'contexto', 'correto', 'correta', 'errado', 'errada', 'exige', 'fragmento', 'hipotética', 'ilustra', 'item', 'itens',
    'julgue', 'marque', 'opção', 'proposição', 'questão', 'seguinte', 'seguintes', 'situação', 'texto', 'tópico', 'trecho',
    'verdadeiro', 'falso', 'cebraspe'
])
