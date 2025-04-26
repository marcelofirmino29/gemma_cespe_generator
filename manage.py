#!/usr/bin/env python

"""Django's command-line utility for administrative tasks."""
import os
import sys

def main():
    """Run administrative tasks."""
    # --- CORREÇÃO AQUI ---
    # Alterado de 'docling_django.settings' para o nome correto do seu projeto
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gemma_cespe_generator.settings')
    # --- FIM DA CORREÇÃO ---
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()