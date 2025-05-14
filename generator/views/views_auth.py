import logging
from django.contrib import messages
from django.shortcuts import redirect, render
from generator.forms import CustomUserCreationForm

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            logger.info(f"Novo usuário cadastrado: {username}")
            messages.success(request, f'Conta criada com sucesso para {username}! Você já pode fazer login.')
            return redirect('login') # Redireciona para a página de login
        else:
            logger.warning(f"Falha no cadastro de usuário: {form.errors.as_json()}")
            # Os erros do formulário serão exibidos no template
    else: # GET request
        form = CustomUserCreationForm()
    context = {'form': form}
    return render(request, 'generator/register.html', context)

logger = logging.getLogger(__name__)