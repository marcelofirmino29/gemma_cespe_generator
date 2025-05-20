# generator/utils.py (MODIFICADO PARA PARSEAR ITENS SEM DEPENDER DE '---' E LIDAR COM ITENS NUMERADOS)
import re
from .exceptions import ParsingError # Supondo que esta exceção personalizada exista
import logging

# Configuração padrão do logger para o módulo atual
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FUNÇÃO 1: Parsing C/E (REESCRITA para: 1 Motivador + N Itens)
# ---------------------------------------------------------------------------
def parse_ai_response_to_questions(text: str) -> tuple[str | None, list[dict]]:
    """
    Faz o parsing do texto C/E no formato: 1 Motivador Principal + N Itens.
    Lida com itens numerados (ex: "**Item 1:**") e não depende mais
    exclusivamente do separador '---' entre os itens.

    Retorna:
        Uma tupla: (texto_motivador_principal, lista_de_questoes)
        onde texto_motivador_principal pode ser None ou string.
        lista_de_questoes é uma lista de dicionários, cada um contendo
        {'afirmacao': str, 'gabarito': str ('C' ou 'E'), 'justificativa': str | None}.
    """
    if not text:
        logger.warning("Parser C/E (Motivador+Itens): Texto de entrada vazio.")
        return None, []
    
    logger.info("Parser C/E (Motivador+Itens): Iniciando parsing...")
    text_cleaned = text.strip()
    main_motivador = None
    questions = []

    # 1. Tenta extrair o Texto Motivador Principal do início
    # Regex ajustado: lookahead para Item agora considera numeração opcional e espaços.
    # Também inclui a possibilidade de '---' ou fim de string '$'.
    motivador_regex = r"\*?\*?Texto Motivador(?: Principal)?:\*?\*?\s*(.*?)(?=\n\s*\n\s*\*?\*?Item\s*\d*:\*?\*?|\n\s*---|$)"
    motivador_match = re.search(motivador_regex, text_cleaned, re.IGNORECASE | re.DOTALL)
    remaining_text_for_items = text_cleaned 

    if motivador_match:
        motivador_content = motivador_match.group(1).strip()
        if motivador_content.lower() != 'não aplicável':
            main_motivador = motivador_content
            logger.info(f"Parser C/E: Texto Motivador Principal encontrado ({len(main_motivador)} chars).")
        else:
            logger.info("Parser C/E: Texto Motivador Principal marcado como 'Não aplicável'.")
        # Atualiza o texto restante para conter apenas a parte dos itens
        remaining_text_for_items = text_cleaned[motivador_match.end():].strip()
    else:
        logger.warning("Parser C/E: Marcador '**Texto Motivador Principal:**' não encontrado no início. Todo o texto será considerado para itens.")

    if not remaining_text_for_items:
        logger.warning("Parser C/E: Não há texto restante para processar os itens após a tentativa de extração do motivador.")
        return main_motivador, []

    # 2. Processa os Itens iterativamente
    # Padrão para encontrar o início de cada item (ex: "**Item 1:**", "**Item:**")
    item_start_pattern = r"\*?\*?Item\s*\d*:\*?\*?\s*"
    
    # Padrões para os marcadores internos de um item
    gabarito_marker_pattern_text = r"Gabarito:"
    justificativa_marker_pattern_text = r"Justificativa:"

    last_item_end = 0
    for item_match_obj in re.finditer(item_start_pattern, remaining_text_for_items, re.IGNORECASE):
        item_block_start = item_match_obj.start()
        
        # Ignora texto entre o fim do último item processado e o início do item atual
        # (pode conter separadores '---' ou lixo, se houver)
        if item_block_start < last_item_end: # Deve ter sido um match dentro de uma justificativa, etc.
            continue

        # Determina o fim do bloco do item atual (início do próximo item ou fim do texto)
        next_item_start_match = re.search(item_start_pattern, remaining_text_for_items[item_match_obj.end():], re.IGNORECASE)
        if next_item_start_match:
            item_block_end = item_match_obj.end() + next_item_start_match.start()
        else:
            item_block_end = len(remaining_text_for_items)
        
        current_item_full_block = remaining_text_for_items[item_block_start : item_block_end].strip()
        # O texto da afirmação está após o header do item atual
        afirmacao_text = current_item_full_block[len(item_match_obj.group(0)):].strip() # .group(0) é o header do item ex: "**Item 1:** "
        
        # Remove o gabarito e justificativa da afirmação, se presentes
        # Procura por Gabarito primeiro
        gabarito_label_match = re.search(r"\n\s*\*?\*?" + gabarito_marker_pattern_text + r"\*?\*?\s*", afirmacao_text, re.IGNORECASE)
        if gabarito_label_match:
            afirmacao_text = afirmacao_text[:gabarito_label_match.start()].strip() # Texto antes de "**Gabarito:**"

        q_data = {'afirmacao': afirmacao_text}

        # Procura por Gabarito no bloco completo do item atual
        gabarito_content_match = re.search(r"\*?\*?" + gabarito_marker_pattern_text + r"\*?\*?\s*(C|E)\b", current_item_full_block, re.IGNORECASE)
        if gabarito_content_match:
            q_data['gabarito'] = gabarito_content_match.group(1).strip().upper()
            if q_data['gabarito'] not in ['C', 'E']:
                logger.warning(f"Parser C/E: Gabarito inválido ('{q_data['gabarito']}') encontrado para o item que começa com: '{afirmacao_text[:50]}...'. Pulando item.")
                last_item_end = item_block_end
                continue
        else:
            logger.warning(f"Parser C/E: Gabarito (C/E) não encontrado para o item que começa com: '{afirmacao_text[:50]}...'. Pulando item.")
            last_item_end = item_block_end
            continue # Gabarito é obrigatório

        # Procura por Justificativa no bloco completo do item atual
        # A justificativa começa após seu marcador e vai até o final do bloco do item atual
        justificativa_content_match = re.search(r"\*?\*?" + justificativa_marker_pattern_text + r"\*?\*?\s*(.*)", current_item_full_block, re.IGNORECASE | re.DOTALL)
        if justificativa_content_match:
            # Precisa garantir que a justificativa extraída não invada o gabarito se a ordem estiver estranha
            # Vamos assumir que a Justificativa vem DEPOIS do Gabarito no bloco.
            # Se o gabarito foi encontrado, a justificativa começa depois dele.
            text_after_gabarito_marker = ""
            if gabarito_content_match:
                 # Pega o fim do match completo do gabarito (marcador + valor C/E)
                end_of_gabarito_match = gabarito_content_match.end()
                text_after_gabarito_marker = current_item_full_block[end_of_gabarito_match:]
                
            # Procura a justificativa no texto APÓS o gabarito
            justificativa_search_in_remaining = re.search(r"\*?\*?" + justificativa_marker_pattern_text + r"\*?\*?\s*(.*)", text_after_gabarito_marker, re.IGNORECASE | re.DOTALL)
            if justificativa_search_in_remaining:
                q_data['justificativa'] = justificativa_search_in_remaining.group(1).strip()
                if not q_data['justificativa']: q_data['justificativa'] = None # Se for string vazia
            else:
                q_data['justificativa'] = None
                logger.debug(f"Parser C/E: Justificativa não encontrada após gabarito para o item: '{afirmacao_text[:50]}...'")
        else:
            q_data['justificativa'] = None
            logger.debug(f"Parser C/E: Marcador de Justificativa não encontrado para o item: '{afirmacao_text[:50]}...'")
        
        if q_data.get('afirmacao') and q_data.get('gabarito'):
            questions.append(q_data)
            logger.debug(f"Parser C/E: Item adicionado: Afirmação='{q_data['afirmacao'][:50]}...', Gabarito='{q_data['gabarito']}'")
        
        last_item_end = item_block_end # Atualiza o cursor para o fim do bloco do item processado

    if not questions and remaining_text_for_items:
        logger.error("Parser C/E: Nenhum item válido pôde ser completamente parseado do texto dos itens.")
    
    logger.info(f"Parser C/E (Motivador+Itens): Parsing finalizado. Motivador: {'Sim' if main_motivador else 'Não'}. Itens parseados: {len(questions)}")
    return main_motivador, questions

# ---------------------------------------------------------------------------
# FUNÇÃO 2: Parsing para Avaliação Discursiva (ESTRUTURA SIMPLIFICADA E CORRIGIDA)
# (Esta função permanece como você a forneceu, pois o problema não está aqui)
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

    NC_PATTERN = r"\*?\*?NC:\*?\*?\s*([+-]?\d+(?:\.\d+)?)"
    NE_PATTERN = r"\*?\*?NE:\*?\*?\s*(\d+)"
    NPD_PATTERN = r"\*?\*?NPD:\*?\*?\s*([+-]?\d+(?:\.\d+)?)"
    JUST_NC_PATTERN = r"\*?\*?Justificativa NC:\*?\*?\s*(.*?)(?=\n\s*\*?\*?[\w\s()]+:\*?\*?|$)"
    COMM_PATTERN = r"\*?\*?Comentários?:\*?\*?\s*(.*?)(?=\n\s*\*?\*?[\w\s()]+:\*?\*?|$)"

    try:
        nc_match = re.search(NC_PATTERN, text, re.IGNORECASE)
        if nc_match:
            try: scores['NC'] = float(nc_match.group(1))
            except (ValueError, TypeError, IndexError): logger.warning(f"Parser Avaliação: Valor NC inválido. Match: '{nc_match.group(0)}'.")
        else: logger.warning("Parser Avaliação: Padrão NC não encontrado.")

        ne_match = re.search(NE_PATTERN, text, re.IGNORECASE)
        if ne_match:
            try: scores['NE'] = int(ne_match.group(1))
            except (ValueError, TypeError, IndexError): logger.warning(f"Parser Avaliação: Valor NE inválido. Match: '{ne_match.group(0)}'.")
        else: logger.warning("Parser Avaliação: Padrão NE não encontrado.")

        npd_match = re.search(NPD_PATTERN, text, re.IGNORECASE)
        if npd_match:
             try: scores['NPD'] = float(npd_match.group(1))
             except (ValueError, TypeError, IndexError): logger.warning(f"Parser Avaliação: Valor NPD inválido. Match: '{npd_match.group(0)}'.")
        else: logger.warning("Parser Avaliação: Padrão NPD não encontrado.")

        just_nc_match = re.search(JUST_NC_PATTERN, text, re.IGNORECASE | re.DOTALL)
        if just_nc_match:
            try: scores['Justificativa_NC'] = just_nc_match.group(1).strip()
            except IndexError: logger.warning(f"Parser Avaliação: Match 'Justificativa NC' encontrado, mas falha ao pegar grupo 1.")
        else: logger.warning("Parser Avaliação: Padrão 'Justificativa NC:' não encontrado.")

        comm_match = re.search(COMM_PATTERN, text, re.IGNORECASE | re.DOTALL)
        if comm_match:
            try: scores['Comentários'] = comm_match.group(1).strip()
            except IndexError: logger.warning(f"Parser Avaliação: Match 'Comentários' encontrado, mas falha ao pegar grupo 1.")
        else: logger.warning("Parser Avaliação: Padrão Comentários não encontrado.")
    except Exception as e:
        logger.error(f"Erro inesperado durante o parsing da avaliação: {e}", exc_info=True)

    # Garante que todas as chaves existam com None como padrão se não encontradas/inválidas
    for key in ['NC', 'NE', 'NPD', 'Justificativa_NC', 'Comentários']:
        scores.setdefault(key, None)

    logger.info(f"Parser Avaliação: Parsing concluído. Resultado: {scores}")
    return scores

# --- Lista de Stop Words (Português) ---
# (Esta lista permanece como você a forneceu)
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
    'viagem', 'vindo', 'vinte', 'vir', 'você', 'vocês', 'vos', 'vós', 'vossa', 'vossas', 'vosso', 'vossos', 'zero', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '_',
    'afirmativa', 'abaixo', 'acerca', 'acima', 'apresentado', 'aspecto', 'assertiva', 'assinale', 'comando', 'conforme',
    'contexto', 'correto', 'correta', 'errado', 'errada', 'exige', 'fragmento', 'hipotética', 'ilustra', 'item', 'itens',
    'julgue', 'marque', 'opção', 'proposição', 'questão', 'seguinte', 'seguintes', 'situação', 'texto', 'tópico', 'trecho',
    'verdadeiro', 'falso', 'cebraspe'
])