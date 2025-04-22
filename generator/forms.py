# generator/forms.py
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
import logging
from .models import AreaConhecimento, Topico

logger = logging.getLogger(__name__)

# --- DEFINIÇÕES GLOBAIS DE CHOICES ---
# <<< LISTA DE ÁREAS ATUALIZADA PARA CONCURSOS >>>
AREA_CHOICES = [
    # O campo ModelChoiceField adicionará '---------' automaticamente se 'empty_label' for usado
    # ou se required=False. Deixaremos a lista começar direto com as áreas.
    ('Administração Financeira e Orçamentária (AFO)', 'AFO'),
    ('Administração Geral', 'Administração Geral'),
    ('Administração Pública', 'Administração Pública'),
    ('Arquivologia', 'Arquivologia'),
    ('Atualidades', 'Atualidades'),
    ('Auditoria', 'Auditoria'),
    ('Contabilidade Geral', 'Contabilidade Geral'),
    ('Contabilidade Pública', 'Contabilidade Pública'),
    ('Direito Administrativo', 'Direito Administrativo'),
    ('Direito Civil', 'Direito Civil'),
    ('Direito Constitucional', 'Direito Constitucional'),
    ('Direito Penal', 'Direito Penal'),
    ('Direito Processual Civil', 'Direito Processual Civil'),
    ('Direito Processual Penal', 'Direito Processual Penal'),
    ('Direito Previdenciário', 'Direito Previdenciário'),
    ('Direito Tributário', 'Direito Tributário'),
    ('Direito do Trabalho', 'Direito do Trabalho'),
    ('Direito Processual do Trabalho', 'Direito Processual do Trabalho'),
    ('Economia', 'Economia'),
    ('Gestão de Pessoas', 'Gestão de Pessoas'),
    ('Informática', 'Informática'),
    ('Inglês', 'Inglês'),
    ('Legislação Específica', 'Legislação Específica'),
    ('Matemática', 'Matemática'),
    ('Português', 'Português'),
    ('Raciocínio Lógico', 'Raciocínio Lógico'),
    ('Outra', 'Outra'),
]

DIFFICULTY_CHOICES = [
    ('', 'Qualquer'),
    ('facil', 'Fácil'),
    ('medio', 'Médio'),
    ('dificil', 'Difícil'),
]

COMPLEXITY_CHOICES = [
    ('Intermediária', 'Intermediária'),
    ('Simples', 'Simples'),
    ('Complexa', 'Complexa'),
]

LANGUAGE_CHOICES = [
    ('pt-br', 'Português (Brasil)'),
    ('en', 'Inglês'),
]
# --- FIM CHOICES ---


# --- Formulário Gerador C/E ---


# --- Formulário Gerador C/E (ATUALIZADO) ---
class QuestionGeneratorForm(forms.Form):
    topic = forms.CharField(
        label="Tópico ou Contexto para Questões C/E", # Label ajustado
        widget=forms.Textarea(attrs={
            'rows': 5, # <<< Linhas aumentadas >>>
            'placeholder': 'Digite o tópico específico (Ex: Controle de Constitucionalidade) ou cole um pequeno texto base...',
            'class': 'form-control',
            'autocomplete': 'off'  # <<< Atributo adicionado para tentar evitar autofill >>>
        }),
        required=True,
        help_text="Descreva o assunto ou forneça um contexto." # Help text ajustado
    )
    num_questions = forms.IntegerField(
        label="Nº Questões",
        min_value=1, # Definido aqui
        initial=3,
        required=True,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'style': 'max-width: 100px;'
            # max é definido no __init__
        })
    )
    difficulty_level = forms.ChoiceField(
        label="Dificuldade",
        # Usa a lista global, mas remove a opção 'Qualquer' (chave vazia)
        choices=[opt for opt in DIFFICULTY_CHOICES if opt[0]],
        required=True, initial='medio',
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 150px;'})
        )
    area = forms.ModelChoiceField(
        queryset=AreaConhecimento.objects.all().order_by('nome'),
        label="Área (Opcional)",
        required=False,
        empty_label="---------", # Texto para opção vazia
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 200px;'}),
        help_text="Ajuda a categorizar."
    )

    def __init__(self, *args, **kwargs):
        # Define o limite máximo de questões dinamicamente
        max_questions_limit = kwargs.pop('max_questions', getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 10)) # Default 10
        super().__init__(*args, **kwargs)
        self.fields['num_questions'].max_value = max_questions_limit
        self.fields['num_questions'].widget.attrs['max'] = max_questions_limit
        self.fields['num_questions'].help_text = f"Gere entre 1 e {max_questions_limit}." # Help text ajustado

    # Validações adicionais
    def clean_topic(self):
        topic = self.cleaned_data.get('topic', '').strip()
        # <<< Validação de comprimento mínimo restaurada >>>
        if len(topic) < 10:
            raise ValidationError("Tópico/Contexto muito curto (mín. 10 caracteres).")
        return topic

    def clean_num_questions(self):
        num = self.cleaned_data.get('num_questions')
        # <<< Validação explícita de min/max restaurada >>>
        if num is not None:
             max_limit = self.fields['num_questions'].max_value
             min_limit = self.fields['num_questions'].min_value
             if min_limit is not None and num < min_limit:
                 raise ValidationError(f"O número mínimo de questões é {min_limit}.")
             if max_limit is not None and num > max_limit:
                 raise ValidationError(f"O número máximo de questões é {max_limit}.")
        # Se for None, a validação required=True já falhou
        return num

# --- Formulário para Gerar Questão Discursiva ---
class DiscursiveExamForm(forms.Form):
    base_topic_or_context = forms.CharField(label="Tópico Geral ou Contexto Base", widget=forms.Textarea(attrs={'rows': 8,'placeholder': 'Forneça o tema geral...','class': 'form-control'}), required=True, help_text="Insumo para IA.")
    num_aspects = forms.IntegerField(label="Nº Aspectos", min_value=1, max_value=5, initial=3, required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'max-width: 120px;'}), help_text="Sub-itens (Padrão: 3).")
    area = forms.ModelChoiceField(
        queryset=AreaConhecimento.objects.all(),
        label="Área de Conhecimento (Opcional)",
        required=False,
        empty_label="Todas as Áreas",
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 250px;'}),
        help_text="Contextualiza vocabulário."
    )
    complexity = forms.ChoiceField(
        label="Complexidade (Opcional)",
        choices=COMPLEXITY_CHOICES,
        required=False, initial='Intermediária',
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 200px;'}), help_text="Profundidade da questão."
    )
    language = forms.ChoiceField(
        label="Idioma",
        choices=LANGUAGE_CHOICES,
        required=False, initial='pt-br',
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 200px;'}), help_text="Idioma da questão gerada."
        )
    def clean_base_topic_or_context(self):
        text = self.cleaned_data.get('base_topic_or_context', '').strip()
        if not text:
            raise ValidationError("O tópico/contexto base deve ser preenchido.")
        return text


# --- Formulário para Geração de Resposta Modelo Discursiva ---
class DiscursiveAnswerForm(forms.Form):
    essay_prompt = forms.CharField(label="Comando da Questão Discursiva", widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'Insira o enunciado...', 'class': 'form-control'}), required=True, help_text="Seja claro.")
    key_points = forms.CharField(label="Pontos-chave (Opcional)", widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Tópicos obrigatórios...', 'class': 'form-control'}), required=False, help_text="Direciona IA.")
    limit = forms.CharField(label="Limite (Opcional)", max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 30 linhas', 'style': 'max-width: 200px;'}), help_text="Ex: 30 linhas.")
    area = forms.ModelChoiceField(
        queryset=AreaConhecimento.objects.all(),
        label="Área de Conhecimento (Opcional)",
        required=False,
        empty_label="Todas as Áreas",
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 250px;'}),
        help_text="Contextualiza."
    )
    def clean_essay_prompt(self):
        prompt = self.cleaned_data.get('essay_prompt', '').strip()
        if not prompt:
            raise ValidationError("O comando da questão discursiva deve ser preenchido.")
        return prompt


# --- Formulário de Cadastro de Usuário ---
class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="E-mail", help_text="Um e-mail válido, por favor.")
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower()
        return email


# --- Formulário de Configuração do Simulado (COM FILTRO DE ÁREA E TÓPICO) ---
class SimuladoConfigForm(forms.Form):
    num_ce = forms.IntegerField(
        label="Nº Questões Certo/Errado", min_value=1, max_value=100, initial=20, required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'max-width: 120px;'}),
        help_text="Quantas questões C/E incluir."
    )
    area = forms.ModelChoiceField(
        queryset=AreaConhecimento.objects.all(),
        label="Área de Conhecimento (Opcional)",
        required=False,
        empty_label="Todas as Áreas",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Filtre questões por área."
    )
    topico = forms.CharField(
        label="Filtrar por Palavras-chave do Tópico (Opcional)",
        max_length=100,
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Ex: controle constitucionalidade, licitação...', 'rows': 3}), # Adicionei 'rows': 3 para altura inicial
        help_text="Busca questões que contenham estas palavras no texto."
    )
    
    dificuldade_ce = forms.ChoiceField(
        label="Dificuldade C/E (Opcional)", choices=DIFFICULTY_CHOICES,
        required=False, widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Filtre questões C/E por dificuldade."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra os tópicos com base na área selecionada (inicialmente todos)
        self.fields['topico'].queryset = Topico.objects.all()
        if 'area' in self.data and self.data['area']:
            try:
                area_id = int(self.data['area'])
                self.fields['topico'].queryset = Topico.objects.filter(area_conhecimento_id=area_id)
            except ValueError:
                pass # Se o valor de 'area' não for um inteiro válido, mantém todos os tópicos

    def clean(self):
        cleaned_data = super().clean()
        # Não há validações adicionais específicas para este formulário no momento
        return cleaned_data