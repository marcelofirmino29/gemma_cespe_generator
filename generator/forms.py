# generator/forms.py
from django import forms
from django.conf import settings

class QuestionGeneratorForm(forms.Form):
    # --- Definir as opções de dificuldade ---
    DIFFICULTY_CHOICES = [
        # ('', '---------'), # Removido para tornar a seleção obrigatória sem opção vazia
        ('facil', 'Fácil'),
        ('medio', 'Médio'),
        ('dificil', 'Difícil'),
        # Adicione mais níveis se necessário
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

    # --- Adicionado o campo de nível de dificuldade ---
    difficulty_level = forms.ChoiceField(
        label="Nível de Dificuldade",
        choices=DIFFICULTY_CHOICES,
        required=True, # Dificuldade é obrigatória
        initial='medio',  # Define 'Médio' como padrão
        widget=forms.Select(attrs={
            'class': 'form-control',
            'style': 'max-width: 200px;' # Ajuste o estilo se necessário
        }),
        help_text="Selecione a dificuldade desejada para as questões."
    )
    # --- Fim da adição ---

    def __init__(self, *args, **kwargs):
        # Obtém o limite das kwargs ou das settings
        max_questions_limit = kwargs.pop('max_questions', settings.AI_MAX_QUESTIONS_PER_REQUEST)
        super().__init__(*args, **kwargs)

        # Define o max_value e o atributo 'max' do widget para num_questions
        self.fields['num_questions'].max_value = max_questions_limit
        self.fields['num_questions'].widget.attrs['max'] = max_questions_limit
        self.fields['num_questions'].help_text = f"Gere entre 1 e {max_questions_limit} questões por vez."

    def clean_topic(self):
        topic = self.cleaned_data.get('topic', '').strip()

        # --- CORRIGIDO: Validar mínimo de 10 caracteres para consistência com a mensagem ---
        if len(topic) < 10:
            raise forms.ValidationError("Descreva o tópico com mais detalhes (mínimo 10 caracteres).")
        # --- FIM CORREÇÃO ---

        # # Tópicos genéricos demais que causam problemas frequentes (mantido comentado)
        # generic_topics = ['redes de computadores', 'direito', 'filosofia', 'história']
        # if topic.lower() in generic_topics:
        #     raise forms.ValidationError("Tente ser mais específico. Por exemplo, em vez de 'redes de computadores', use 'Modelo OSI' ou 'Protocolos TCP/IP'.")

        return topic

    def clean_num_questions(self):
        num = self.cleaned_data.get('num_questions')
        # --- MELHORADO: Obter max_limit diretamente do campo como definido no __init__ ---
        max_limit = self.fields['num_questions'].max_value
        # --- FIM MELHORIA ---

        if num is not None and num > max_limit:
            # A mensagem de erro usa o f-string corretamente
            raise forms.ValidationError(f"O número máximo de questões permitido é {max_limit}.")

        return num

    # Não é necessário um clean_difficulty_level se a única validação
    # for garantir que a escolha está entre as opções válidas (o ChoiceField já faz isso).