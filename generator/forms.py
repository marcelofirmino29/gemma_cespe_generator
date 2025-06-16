# generator/forms.py
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
import logging
from .models import AreaConhecimento, Topico, Questao, KahootGame

logger = logging.getLogger(__name__)

# --- DEFINIÇÕES GLOBAIS DE CHOICES ---
DIFFICULTY_CHOICES = [
    ('', 'Qualquer'),
    ('facil', 'Fácil'),
    ('medio', 'Médio'),
    ('dificil', 'Difícil'),
]

COMPLEXITY_CHOICES = [
    ('Simples', 'Simples'),
    ('Intermediária', 'Intermediária'),
    ('Complexa', 'Complexa'),
]

LANGUAGE_CHOICES = [
    ('pt-br', 'Português (Brasil)'),
    ('en', 'Inglês'),
]


class QuestionGeneratorForm(forms.Form):
    topic = forms.CharField(
        label="Tópico ou Contexto para Questões C/E",
        widget=forms.Textarea(attrs={
            'rows': 5,
            'placeholder': 'Digite o tópico específico (Ex: Controle de Constitucionalidade) ou cole um pequeno texto base...',
            'class': 'form-control',
            'id': 'id_topic',
            'autocomplete': 'off'
        }),
        required=True,
        help_text="Descreva o assunto ou forneça um contexto. Mín. 4 caracteres se este for o input."
    )
    
    pdf_contexto = forms.FileField(
        label="OU Envie um PDF para Contexto",
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control form-control-sm',
            'id': 'id_pdf_contexto_ce_generator',
            'accept': '.pdf'
        }),
        help_text="Se um PDF for enviado, o campo 'Tópico ou Contexto' textual acima se torna opcional."
    )

    num_questions = forms.IntegerField(
        label="Nº Questões",
        min_value=1,
        initial=3,
        required=True,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'id': 'id_num_questions_ce_generator'
        })
    )
    difficulty_level = forms.ChoiceField(
        label="Dificuldade",
        choices=[opt for opt in DIFFICULTY_CHOICES if opt[0]],
        required=True, initial='medio',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            'id': 'id_difficulty_ce_generator'
            })
    )
    area = forms.ModelChoiceField(
        queryset=AreaConhecimento.objects.all().order_by('nome'),
        label="Área de Conhecimento",
        required=True,
        empty_label="-- Selecione a Área --",
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            'id': 'id_area_ce_generator'
            }),
        help_text="Selecione a área para as novas questões geradas."
    )

    def __init__(self, *args, **kwargs):
        max_questions_limit = kwargs.pop('max_questions', getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 10))
        super().__init__(*args, **kwargs)
        
        if 'num_questions' in self.fields:
            self.fields['num_questions'].max_value = max_questions_limit
            self.fields['num_questions'].widget.attrs['max'] = max_questions_limit
            min_val = self.fields['num_questions'].min_value or 1 
            self.fields['num_questions'].help_text = f"Gere entre {min_val} e {max_questions_limit}."

    def clean(self):
        cleaned_data = super().clean()
        topic = cleaned_data.get('topic', '').strip()
        pdf_contexto = cleaned_data.get('pdf_contexto')

        if not topic and not pdf_contexto:
            error_message = "Forneça um Tópico/Contexto textual OU envie um arquivo PDF."
            self.add_error('topic', ValidationError(error_message, code='input_required'))
            self.add_error('pdf_contexto', ValidationError(error_message, code='input_required'))

        return cleaned_data

class DiscursiveExamForm(forms.Form):
    base_topic_or_context = forms.CharField(
        label="Tópico Geral ou Contexto Base (Opcional se PDF fornecido)",
        widget=forms.Textarea(attrs={
            'rows': 6,
            'placeholder': 'Forneça o tema geral, ou cole um texto base, ou envie um PDF abaixo...',
            'class': 'form-control',
            'id': 'id_base_topic_discursive'
        }),
        required=False,
        help_text="Insira o tópico/contexto manualmente OU envie um arquivo PDF."
    )
    pdf_file = forms.FileField(
        label="OU Envie um Arquivo PDF como Contexto",
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'accept': '.pdf',
            'class': 'form-control form-control-sm mt-2',
            'id': 'id_pdf_file_discursive'
        }),
        help_text="Se um PDF for enviado, seu conteúdo será usado como base para a questão."
    )
    num_aspects = forms.IntegerField(
        label="Nº Aspectos", min_value=1, max_value=7, initial=3, required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
        help_text="Sub-itens da questão (Padrão: 3)."
    )
    area = forms.ModelChoiceField(
        queryset=AreaConhecimento.objects.all().order_by('nome'),
        label="Área de Conhecimento", required=False, empty_label="-- Qualquer Área --",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        help_text="Contextualiza a questão."
    )
    complexity = forms.ChoiceField(
        label="Complexidade", choices=COMPLEXITY_CHOICES, required=True, initial='Intermediária',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        help_text="Define a profundidade."
    )
    language = forms.ChoiceField(
        label="Idioma", choices=LANGUAGE_CHOICES, required=True, initial='pt-br',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        help_text="Idioma da questão gerada."
    )

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('base_topic_or_context') and not cleaned_data.get('pdf_file'):
            raise ValidationError("Por favor, forneça um Tópico/Contexto textual OU envie um arquivo PDF.", code='required_source')
        return cleaned_data

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="E-mail", help_text="Um e-mail válido, por favor.")
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

class SimuladoConfigForm(forms.Form):
    num_ce = forms.IntegerField(
        label="Nº Questões Certo/Errado", min_value=1, max_value=100, initial=20, required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'max-width: 120px;'}),
        help_text="Quantas questões C/E incluir."
    )
    area = forms.ModelChoiceField(
        queryset=AreaConhecimento.objects.all(), label="Área de Conhecimento (Opcional)", required=False,
        empty_label="Todas as Áreas", widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Filtre questões por área."
    )
    topico = forms.CharField(
        label="Filtrar por Palavras-chave do Tópico (Opcional)", max_length=100, required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Ex: controle constitucionalidade, licitação...', 'rows': 3}),
        help_text="Busca questões que contenham estas palavras no texto."
    )
    dificuldade_ce = forms.ChoiceField(
        label="Dificuldade C/E (Opcional)", choices=DIFFICULTY_CHOICES, required=False, 
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Filtre questões C/E por dificuldade."
    )

class AskAIForm(forms.Form):
    user_input = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Digite sua pergunta para a IA...'}),
        label="Sua Pergunta à IA",
        required=True
    )

class AreaConhecimentoForm(forms.ModelForm):
    class Meta:
        model = AreaConhecimento
        fields = ['nome']
        widgets = { 'nome': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ex: Direito Administrativo'}) }
        labels = { 'nome': 'Nome da Nova Área de Conhecimento' }
        help_texts = { 'nome': 'O nome deve ser único.' }

    def clean_nome(self):
        nome = self.cleaned_data.get('nome')
        if nome:
            query = AreaConhecimento.objects.filter(nome__iexact=nome)
            if self.instance and self.instance.pk:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise ValidationError("Já existe uma Área de Conhecimento com este nome.")
        return nome

class PDFUploadForm(forms.Form):
    pdf_file = forms.FileField(
        label='Selecione o arquivo PDF',
        help_text='Máximo de 50MB. Apenas arquivos .pdf são permitidos.',
        widget=forms.ClearableFileInput(attrs={'accept': '.pdf', 'class': 'form-control'})
    )
    num_questions_ce = forms.IntegerField(
        label='Número de Questões Certo/Errado', min_value=0, max_value=20, initial=5, required=False,
        help_text='Deixe em 0 ou em branco se não desejar questões C/E.',
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    num_aspects_discursive = forms.IntegerField(
        label='Número de Aspectos para Questão Discursiva', min_value=0, max_value=5, initial=3, required=False,
        help_text='Deixe em 0 ou em branco se não desejar questão discursiva.',
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    difficulty_level = forms.ChoiceField(
        label='Nível de Dificuldade', choices=[('facil', 'Fácil'), ('medio', 'Médio'), ('dificil', 'Difícil')],
        initial='medio', required=True, widget=forms.Select(attrs={'class': 'form-select'})
    )
    area = forms.ModelChoiceField(
        queryset=AreaConhecimento.objects.all().order_by('nome'), required=False, 
        label="Área de Conhecimento (Opcional)",
        help_text="Selecione uma área para associar às questões geradas.",
        widget=forms.Select(attrs={'class': 'form-select'}), empty_label="-- Nenhuma Área Específica --" 
    )

class PDFSummaryForm(forms.Form):
    pdf_file = forms.FileField(
        label='Selecione o arquivo PDF para resumir',
        help_text='Máximo de 50MB. Apenas arquivos .pdf são permitidos.',
        widget=forms.ClearableFileInput(attrs={'accept': '.pdf', 'class': 'form-control'})
    )

# --- NOVOS FORMULÁRIOS PARA O EDITOR DE QUIZ MANUAL ---

class QuizForm(forms.ModelForm):
    """
    Formulário para criar o título de um novo Quiz (modelo de KahootGame).
    """
    class Meta:
        model = KahootGame
        fields = ['title']
        labels = {
            'title': 'Título do Quiz'
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ex: Revisão de Direito Administrativo'})
        }

class QuestionForm(forms.ModelForm):
    """
    Formulário para adicionar ou editar uma questão de múltipla escolha manualmente.
    """
    class Meta:
        model = Questao
        fields = ['enunciado', 'alternativa_a', 'alternativa_b', 'alternativa_c', 'alternativa_d', 'gabarito_me', 'tempo_limite']
        labels = {
            'enunciado': 'Texto da Pergunta',
            'alternativa_a': 'Alternativa A',
            'alternativa_b': 'Alternativa B',
            'alternativa_c': 'Alternativa C',
            'alternativa_d': 'Alternativa D',
            'gabarito_me': 'Resposta Correta',
            'tempo_limite': 'Tempo para Responder (em segundos)'
        }
        widgets = {
            'enunciado': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'alternativa_a': forms.TextInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Obrigatória'}),
            'alternativa_b': forms.TextInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Obrigatória'}),
            'alternativa_c': forms.TextInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Opcional'}),
            'alternativa_d': forms.TextInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Opcional'}),
            'gabarito_me': forms.Select(attrs={'class': 'form-select'}),
            'tempo_limite': forms.NumberInput(attrs={'class': 'form-control', 'value': 20}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['gabarito_me'].choices = [('', '---------')] + self.fields['gabarito_me'].choices[1:]
        self.fields['alternativa_a'].required = True
        self.fields['alternativa_b'].required = True