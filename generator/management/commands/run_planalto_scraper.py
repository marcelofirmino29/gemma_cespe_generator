# generator/management/commands/run_planalto_scraper.py
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import logging

# Importe a função principal do seu scraper de leis do Planalto
# Ajuste o caminho do import se 'scraper_leis_planalto.py' estiver em outro lugar
# ou se você usou uma classe.
try:
    from generator.scraper_leis_planalto import run_planalto_leis_scraper_main
except ImportError:
    run_planalto_leis_scraper_main = None # Para evitar erro na definição da classe Command

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Executa o scraper de Leis do Planalto e salva no banco de dados.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-depth',
            type=int,
            # Pega o default do settings ou define um valor aqui
            default=getattr(settings, 'SCRAPER_CONFIG_PLANALTO', {}).get('MAX_DEPTH', 6),
            help='Profundidade máxima de recursão para o scraper de leis (default: 1).'
        )
        parser.add_argument(
            '--start-url',
            type=str,
            default=getattr(settings, 'SCRAPER_CONFIG_PLANALTO', {}).get('START_URL', None),
            help='URL inicial para o scraper de leis (default: usa a URL base do scraper).'
        )
        # Adicione mais argumentos se a sua função run_planalto_leis_scraper_main aceitar

    def handle(self, *args, **options):
        if not run_planalto_leis_scraper_main:
            raise CommandError("A função do scraper 'run_planalto_leis_scraper_main' não pôde ser importada. Verifique 'generator/scraper_leis_planalto.py'.")

        max_depth = options['max_depth']
        start_url = options['start_url']

        self.stdout.write(self.style.NOTICE(f"Iniciando coleta de Leis do Planalto... Profundidade: {max_depth}, URL Inicial: {start_url or 'Padrão'}"))
        logger.info(f"Comando run_planalto_scraper: Iniciando com max_depth={max_depth}, start_url={start_url}")

        try:
            # Chame a função principal do seu scraper de leis
            run_planalto_leis_scraper_main(max_depth=max_depth, start_url=start_url)
            self.stdout.write(self.style.SUCCESS('Scraper de Leis do Planalto executado com sucesso.'))
            logger.info("Comando run_planalto_scraper: Execução concluída com sucesso.")
        except Exception as e:
            logger.error(f"Comando run_planalto_scraper: Erro ao executar o scraper de leis: {e}", exc_info=True)
            # Levantar CommandError fará com que o manage.py saia com status de erro
            raise CommandError(f"Erro ao executar o scraper de leis: {e}")