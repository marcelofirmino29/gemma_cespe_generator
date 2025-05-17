# generator/exceptions.py

class GeneratorError(Exception):
    """Classe base para exceções do módulo generator."""

class ConfigurationError(GeneratorError): # Adicionada para erros de setup
    """Erro relacionado à configuração inicial."""

class AIServiceError(GeneratorError):
    """Erro relacionado à comunicação ou configuração do serviço de IA."""

class AIResponseError(GeneratorError):
    """Erro relacionado ao conteúdo ou formato da resposta da IA."""

class ParsingError(GeneratorError):
    """Erro durante o parsing da resposta da IA."""
