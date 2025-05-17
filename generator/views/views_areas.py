from django.contrib import messages
from venv import logger
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from generator.forms import AreaConhecimentoForm
from generator.models import AreaConhecimento
from venv import logger
from django.views.decorators.http import require_POST

from generator.views.views_service_context import _get_base_context_and_service
# # --- Sua função _get_base_context_and_service ---

@login_required # Apenas usuários logados podem ver/gerenciar
def area_list_view(request):
    """Lista todas as Áreas de Conhecimento cadastradas."""
    context, _, _ = _get_base_context_and_service()
    try:
        areas = AreaConhecimento.objects.all().order_by('nome') # Busca todas as áreas ordenadas
        context['areas'] = areas
    except Exception as e:
        logger.error(f"Erro ao listar Áreas de Conhecimento: {e}", exc_info=True)
        messages.error(request, "Erro ao carregar a lista de áreas.")
        context['areas'] = [] # Retorna lista vazia em caso de erro

    return render(request, 'generator/area_list.html', context)

@login_required
@require_POST # Garante que só aceite requisições POST
def add_area_quick_from_generator_view(request):
    """
    Processa a submissão do formulário de adição rápida de Área de Conhecimento
    a partir da página do gerador C/E e redireciona de volta.
    """
    # Instancia o formulário com os dados recebidos via POST
    form = AreaConhecimentoForm(request.POST)

    # Verifica se os dados do formulário são válidos
    if form.is_valid():
        try:
            # Cria o objeto AreaConhecimento sem salvar no banco ainda
            nova_area = form.save(commit=False)
            # Opcional: Associar o usuário que criou
            # nova_area.criado_por = request.user
            # Salva o objeto no banco de dados
            nova_area.save()
            # Obtém o nome da área salva para a mensagem
            nome_area = form.cleaned_data.get('nome')
            # Adiciona uma mensagem de sucesso para o usuário
            messages.success(request, f"Área '{nome_area}' adicionada com sucesso!")
            # Loga a ação
            logger.info(f"Área rápida adicionada (via Gerador C/E): '{nome_area}' por {request.user.username}")
        except Exception as e:
             # Em caso de erro ao salvar (ex: problema no DB)
             nome_area_tentativa = form.cleaned_data.get('nome', '[N/A]') # Pega nome se disponível
             logger.error(f"Erro ao salvar área rápida (via Gerador C/E) '{nome_area_tentativa}': {e}", exc_info=True)
             messages.error(request, f"Ocorreu um erro inesperado ao tentar salvar a área '{nome_area_tentativa}'.")
    else:
        # Se o formulário for inválido (ex: nome duplicado, vazio, etc.)
        # Constrói uma mensagem de erro a partir dos erros do formulário
        # Pega a primeira mensagem de erro de qualquer campo, se houver
        error_list = [f"{field}: {error[0]}" for field, error in form.errors.items()]
        erro_msg = "Erro ao adicionar área: " + (error_list[0] if error_list else "Verifique os dados.")
        # Loga os erros detalhados
        logger.warning(f"Tentativa inválida de adicionar Área Rápida (via Gerador C/E) por {request.user.username}: {form.errors.as_json()}")
        # Adiciona a mensagem de erro para o usuário
        messages.error(request, erro_msg)

    # Redireciona de volta para a página do gerador C/E,
    # independentemente de ter tido sucesso ou falha na adição da área.
    # As mensagens (success ou error) serão exibidas na página recarregada.
    return redirect('generator:generate_questions')
