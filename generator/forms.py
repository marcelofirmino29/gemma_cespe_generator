# generator/forms.py         
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError # Garanta que está importado no topo do forms.py

# --- Constantes de Choices (Opcional: definir aqui para reutilização) ---
AREA_CHOICES = [
    ('', '---------'),                         # Placeholder
    ('Informática', 'Informática'),             # Primeira Opção
    ('Português', 'Português (Teoria)'),        # Segunda Opção
    ('Administração', 'Administração'),        # Início Ordem Alfabética
    ('Atualidades', 'Atualidades'),
    ('Direito', 'Direito'),
    ('Economia', 'Economia'),
    ('Mercado de Seguros', 'Mercado de Seguros'), # <<< ADICIONADO AQUI
    ('Políticas Públicas', 'Políticas Públicas'),
    ('Sociologia', 'Sociologia'),
    # Adicione outras áreas aqui, mantendo a ordem alfabética se desejar
    ('Outra', 'Outra'),                         # Última opção específica
]

# --- Formulário Gerador C/E ---
class QuestionGeneratorForm(forms.Form):
    DIFFICULTY_CHOICES = [
        ('facil', 'Fácil'),
        ('medio', 'Médio'),
        ('dificil', 'Difícil'),
    ]

    topic = forms.CharField(
        label="Tópico/Assunto",
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Ex: Direito Constitucional - Controle de Constitucionalidade',
            'class': 'form-control'
        }),
        required=True,
        help_text="Descreva o assunto de forma específica para gerar melhores questões."
    )

    num_questions = forms.IntegerField(
        label="Número de Questões",
        min_value=1,
        initial=3,
        required=True,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'style': 'max-width: 100px;'
        })
    )

    difficulty_level = forms.ChoiceField(
        label="Nível de Dificuldade",
        choices=DIFFICULTY_CHOICES,
        required=True,
        initial='medio',
        widget=forms.Select(attrs={
            'class': 'form-select', # Mudado para form-select para consistência Bootstrap
            'style': 'max-width: 200px;'
        }),
        help_text="Selecione a dificuldade desejada para as questões."
    )

    def __init__(self, *args, **kwargs):
        max_questions_limit = kwargs.pop('max_questions', getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 5)) # Use getattr para segurança
        super().__init__(*args, **kwargs)
        self.fields['num_questions'].max_value = max_questions_limit
        self.fields['num_questions'].widget.attrs['max'] = max_questions_limit
        self.fields['num_questions'].help_text = f"Gere entre 1 e {max_questions_limit} questões por vez."

    def clean_topic(self):
        topic = self.cleaned_data.get('topic', '').strip()
        if len(topic) < 5:
            raise forms.ValidationError("Descreva o tópico com mais detalhes (mínimo 5 caracteres).")
        # Validação de tópicos genéricos (opcional) mantida comentada
        # ...
        return topic

    def clean_num_questions(self):
        num = self.cleaned_data.get('num_questions')
        max_limit = self.fields['num_questions'].max_value
        if num is not None: # Validação de max_value já é feita pelo IntegerField, mas podemos reforçar
             if num > max_limit:
                 raise forms.ValidationError(f"O número máximo de questões permitido é {max_limit}.")
             if num < self.fields['num_questions'].min_value: # Valida mínimo também explicitamente
                  raise forms.ValidationError(f"O número mínimo de questões permitido é {self.fields['num_questions'].min_value}.")
        # Se num is None, a validação 'required=True' já deve ter falhado antes
        return num

# --- Formulário para Gerar a PERGUNTA/EXAME Discursivo (MERGIDO E CORRIGIDO) ---
class DiscursiveExamForm(forms.Form):
    # Usando AREA_CHOICES definido no início do arquivo
    COMPLEXITY_CHOICES = [
        ('Intermediária', 'Intermediária'),
        ('Simples', 'Simples'),
        ('Complexa', 'Complexa'),
    ]
    LANGUAGE_CHOICES = [
        ('pt-br', 'Português (Brasil)'),
        ('en', 'Inglês'),
        # Adicione outros idiomas se desejar
    ]

    base_topic_or_context = forms.CharField(
        label="Tópico Geral ou Contexto Base",
        widget=forms.Textarea(attrs={
            'rows': 8,
            'placeholder': 'Forneça o tema geral (ex: Responsabilidade Civil do Estado, Reforma Tributária) ou cole um texto base (ex: um artigo de lei, uma notícia) a partir do qual a prova discursiva será elaborada...',
            'class': 'form-control'
        }),
        required=True,
        help_text="Este será o insumo para a IA criar os textos motivadores, o comando e os aspectos da questão."
    )

    num_aspects = forms.IntegerField(
        label="Nº de Aspectos a Cobrar",
        min_value=1,
        max_value=5, # Limite razoável
        initial=3,
        required=False, # Opcional, default tratado na view/serviço
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'max-width: 120px;'}),
        help_text="Quantos sub-itens a resposta deve abordar (Padrão: 3)."
    )

    area = forms.ChoiceField(
        label="Área de Conhecimento (Opcional)",
        choices=AREA_CHOICES, # Reutilizando choices definidos acima
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 250px;'}),
        help_text="Ajuda a IA a definir o vocabulário e o tipo de texto motivador."
    )

    complexity = forms.ChoiceField(
        label="Complexidade da Questão (Opcional)",
        choices=COMPLEXITY_CHOICES,
        required=False,
        initial='Intermediária',
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 200px;'}),
        help_text="Define a profundidade esperada da questão e dos aspectos."
    )

    # <<< CAMPO ADICIONADO DA SEGUNDA DEFINIÇÃO >>>
    language = forms.ChoiceField(
        label="Idioma da Questão",
        choices=LANGUAGE_CHOICES,
        required=False, # Tornar opcional, default será pt-br na view/serviço
        initial='pt-br',
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 200px;'}),
        help_text="Selecione o idioma desejado para a questão gerada."
    )
    # <<< FIM DA ADIÇÃO >>>

    def clean_base_topic_or_context(self):
        text = self.cleaned_data.get('base_topic_or_context', '').strip()
        if len(text) < 5: # Validação mínima mantida
            raise ValidationError("Forneça um tópico ou contexto com mais detalhes (mínimo 5 caracteres).")
        return text

# --- Formulário para Geração de Resposta Discursiva Modelo ---
class DiscursiveAnswerForm(forms.Form):
    # Usando AREA_CHOICES definido no início do arquivo
    essay_prompt = forms.CharField(
        label="Comando da Questão Discursiva",
        widget=forms.Textarea(attrs={
            'rows': 5,
            'placeholder': 'Insira aqui o enunciado completo da questão discursiva...',
            'class': 'form-control'
        }),
        required=True,
        help_text="Seja o mais claro possível no comando da questão."
    )

    key_points = forms.CharField(
        label="Pontos-chave a Abordar (Opcional)",
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Liste aqui tópicos ou argumentos que a resposta DEVE conter (um por linha)...',
            'class': 'form-control'
        }),
        required=False,
        help_text="Ajuda a direcionar a IA para incluir informações específicas."
    )

    limit = forms.CharField(
        label="Limite de Tamanho (Opcional)",
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 30 linhas', 'style': 'max-width: 200px;'}),
        help_text="Informe o limite da prova (ex: 30 linhas, 500 palavras)."
    )

    area = forms.ChoiceField(
        label="Área de Conhecimento (Opcional)",
        choices=AREA_CHOICES, # Reutilizando choices definidos acima
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 250px;'}),
        help_text="Ajuda a IA a contextualizar a resposta e o vocabulário."
    )

    def clean_essay_prompt(self):
        prompt = self.cleaned_data.get('essay_prompt', '').strip()
        if len(prompt) < 5: # Validação mínima mantida
            raise ValidationError("O comando da questão parece muito curto (mínimo 5 caracteres).")
        return prompt
    
# No final de generator/forms.py

from django import forms
# Importa o UserCreationForm padrão e o model User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User # Ou importe settings.AUTH_USER_MODEL se usar custom user

# --- Formulário de Cadastro de Usuário ---
class CustomUserCreationForm(UserCreationForm):
    # Adicionamos o campo de email, que não vem por padrão no UserCreationForm
    email = forms.EmailField(
        required=True,
        label="E-mail",
        help_text="Um e-mail válido, por favor."
    )

    class Meta(UserCreationForm.Meta): # Herda a Meta do UserCreationForm
        model = User # Especifica que este form cria um objeto User
        # Define os campos do MODEL User que este form vai exibir/salvar,
        # ALÉM dos campos de senha que já são tratados pelo UserCreationForm.
        fields = ('username', 'email')

    # Opcional: Adicionar validação para email único, se desejado
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Este endereço de e-mail já está em uso.")
        return email

    # Não precisamos redefinir o método save() se apenas adicionamos campos
    # que já existem no model User e estão listados em Meta.fields.
    # O save() do UserCreationForm pai cuidará de criar o usuário e salvar a senha hash.v