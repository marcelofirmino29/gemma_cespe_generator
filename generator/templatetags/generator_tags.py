# generator/templatetags/generator_tags.py
from django import template
from urllib.parse import urlencode

register = template.Library()

@register.simple_tag(takes_context=True) # Adicionado takes_context=True
def url_params(context, **kwargs):
    """
    Pega os parâmetros GET atuais do request no contexto,
    atualiza/remove com os kwargs fornecidos, e retorna a query string formatada.
    Ex: <a href="?page={{ num }}{% url_params page=None %}">
    """
    # Pega o QueryDict 'GET' do objeto request no contexto
    querydict = context['request'].GET.copy()
    for key, value in kwargs.items():
        if value is not None and value != '': # Trata valor vazio como não existente também
            querydict[key] = value
        else:
            querydict.pop(key, None) # Remove chave se valor for None ou vazio

    if querydict:
        # Adiciona & no início pois será concatenado com ?page=...
        return f"&{querydict.urlencode()}"
    return ""