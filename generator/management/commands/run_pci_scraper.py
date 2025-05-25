# generator/management/commands/run_pci_scraper.py
from django.core.management.base import BaseCommand
from generator.scraper_provas_pci import PCIConcursosScraper # Ajuste o import
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Executa o scraper de provas do PCI Concursos e salva no banco de dados.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-categorias',
            type=int,
            help='Número máximo de categorias de cargo para processar.'
        )
        parser.add_argument(
            '--max-paginas',
            type=int,
            help='Número máximo de páginas por categoria.'
        )
        parser.add_argument(
            '--ano',
            type=str,
            help='Ano específico para focar (ex: "2023").'
        )
        parser.add_argument(
            '--profundidade',
            type=int,
            help='Profundidade máxima de recursão em sublinks.'
        )

    def handle(self, *args, **options):
        logger.info("Iniciando o comando run_pci_scraper...")

        # Obter configurações padrão do settings.py
        default_config = settings.SCRAPER_CONFIG_PCICONCURSOS

        # Override com argumentos da linha de comando se fornecidos
        max_cat = options['max_categorias'] if options['max_categorias'] is not None else default_config.get('MAX_CATEGORIAS_CARGO')
        max_pag = options['max_paginas'] if options['max_paginas'] is not None else default_config.get('MAX_PAGINAS_POR_CATEGORIA')
        ano_a = options['ano'] if options['ano'] is not None else default_config.get('ANO_ALVO')
        max_prof = options['profundidade'] if options['profundidade'] is not None else default_config.get('MAX_PROFUNDIDADE_RECURSAO')

        scraper = PCIConcursosScraper(
            max_categorias_cargo=max_cat,
            max_paginas_por_categoria=max_pag,
            ano_alvo=ano_a,
            max_profundidade_recursao=max_prof
        )

        try:
            scraper.run_scraper()
            logger.info("Scraper executado com sucesso.")
            self.stdout.write(self.style.SUCCESS('Scraper executado com sucesso.'))
        except Exception as e:
            logger.error(f"Erro ao executar o scraper: {e}", exc_info=True)
            self.stderr.write(self.style.ERROR(f"Erro ao executar o scraper: {e}"))