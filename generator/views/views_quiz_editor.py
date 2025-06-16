# generator/views/views_quiz_editor.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from ..models import KahootGame, Questao
from ..forms import QuizForm, QuestionForm

@login_required
def quiz_list_view(request):
    # Lista apenas os quizzes criados pelo usuário logado que são modelos
    quizzes = KahootGame.objects.filter(host=request.user, is_template=True).order_by('-created_at')
    return render(request, 'generator/quiz_editor/quiz_list.html', {'quizzes': quizzes})

@login_required
def quiz_create_view(request):
    if request.method == 'POST':
        form = QuizForm(request.POST)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.host = request.user
            quiz.is_template = True # Marca como um modelo de quiz
            quiz.status = 'waiting' # Status padrão, não importa para o modelo
            quiz.save()
            messages.success(request, f"Quiz '{quiz.title}' criado com sucesso! Agora adicione perguntas.")
            return redirect('generator:quiz_edit', pk=quiz.pk)
    else:
        form = QuizForm()
    return render(request, 'generator/quiz_editor/quiz_form.html', {'form': form})

@login_required
def quiz_edit_view(request, pk):
    quiz = get_object_or_404(KahootGame, pk=pk, is_template=True)
    if quiz.host != request.user:
        return HttpResponseForbidden("Você não tem permissão para editar este quiz.")

    if request.method == 'POST': # Lógica para adicionar uma nova questão
        question_form = QuestionForm(request.POST)
        if question_form.is_valid():
            question = question_form.save(commit=False)
            question.tipo = 'ME' # Garante que é múltipla escolha
            question.criado_por = request.user
            question.save()
            quiz.questoes.add(question)
            messages.success(request, "Pergunta adicionada com sucesso!")
            return redirect('generator:quiz_edit', pk=quiz.pk)
    else:
        question_form = QuestionForm()

    questions = quiz.questoes.all()
    return render(request, 'generator/quiz_editor/quiz_editor.html', {
        'quiz': quiz,
        'questions': questions,
        'question_form': question_form
    })

@login_required
def quiz_delete_view(request, pk):
    quiz = get_object_or_404(KahootGame, pk=pk, is_template=True)
    if quiz.host != request.user:
        return HttpResponseForbidden("Você não tem permissão para excluir este quiz.")
    
    if request.method == 'POST':
        quiz_title = quiz.title
        quiz.delete()
        messages.success(request, f"Quiz '{quiz_title}' excluído com sucesso.")
        return redirect('generator:quiz_list')
        
    return render(request, 'generator/quiz_editor/quiz_confirm_delete.html', {'quiz': quiz})

@login_required
def quiz_launch_view(request, pk):
    quiz_template = get_object_or_404(KahootGame, pk=pk, is_template=True)
    if quiz_template.host != request.user:
        return HttpResponseForbidden("Você não pode lançar um quiz que não é seu.")

    if not quiz_template.questoes.exists():
        messages.error(request, "Este quiz não pode ser lançado porque não tem perguntas.")
        return redirect('generator:quiz_edit', pk=pk)

    # Cria um novo jogo ao vivo como uma cópia do modelo
    live_game = KahootGame.objects.create(
        host=request.user,
        title=quiz_template.title,
        is_template=False, # Este é um jogo ao vivo
        status='waiting',
    )
    live_game.questoes.set(quiz_template.questoes.all())
    
    # Redireciona para a tela de host do jogo ao vivo
    return redirect('generator:kahoot_host', game_pin=live_game.pin)