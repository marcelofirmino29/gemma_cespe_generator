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
    ('Simples', 'Simples'),
    ('Intermediária', 'Intermediária'),
    ('Complexa', 'Complexa'),
]

LANGUAGE_CHOICES = [
    ('pt-br', 'Português (Brasil)'),
    ('en', 'Inglês'),
]
# No seu arquivo forms.py (ex: generator/forms.py)

from django import forms
from django.conf import settings # Para getattr(settings, ...)
from django.core.exceptions import ValidationError
from .models import AreaConhecimento # Certifique-se que o import está correto

# Supondo que DIFFICULTY_CHOICES está definido globalmente ou importado
# Exemplo (certifique-se que corresponde ao seu):
DIFFICULTY_CHOICES = [
    ('facil', 'Fácil'),
    ('medio', 'Médio'),
    ('dificil', 'Difícil'),
    # ('qualquer', 'Qualquer'), # Removido pelo seu código se a chave for vazia
]

class QuestionGeneratorForm(forms.Form):
    topic = forms.CharField(
        label="Tópico ou Contexto para Questões C/E",
        widget=forms.Textarea(attrs={
            'rows': 5,
            'placeholder': 'Digite o tópico específico (Ex: Controle de Constitucionalidade) ou cole um pequeno texto base...',
            'class': 'form-control',
            'id': 'id_topic', # Para o JavaScript no template
            'autocomplete': 'off'
        }),
        required=True,  # Permanece True para a validação HTML5 inicial e se nenhum PDF for enviado.
                        # A view ajustará para False se um PDF for detectado ANTES de form.is_valid().
        help_text="Descreva o assunto ou forneça um contexto. Mín. 4 caracteres se este for o input."
    )
    
    # --- NOVO CAMPO ADICIONADO ---
    pdf_contexto = forms.FileField(
        label="OU Envie um PDF para Contexto",
        required=False, # Este campo em si não é obrigatório; a lógica 'pelo menos um' está no clean().
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control form-control-sm', # Para consistência com outros inputs de arquivo
            'id': 'id_pdf_contexto_ce_generator', # ID usado no template para o JS
            'accept': '.pdf'
        }),
        help_text="Se um PDF for enviado, o campo 'Tópico ou Contexto' textual acima se torna opcional."
    )
    # --- FIM DO NOVO CAMPO ---

    num_questions = forms.IntegerField(
        label="Nº Questões",
        min_value=1,
        initial=3,
        required=True,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm', # Aplicando form-control-sm para consistência
            # 'style': 'max-width: 100px;' # Estilo é melhor via CSS global se possível
            'id': 'id_num_questions_ce_generator' # ID para o JS do template
        })
    )
    difficulty_level = forms.ChoiceField(
        label="Dificuldade",
        choices=[opt for opt in DIFFICULTY_CHOICES if opt[0]], # Remove opções com chave vazia
        required=True, initial='medio',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm', # Aplicando form-select-sm
            # 'style': 'max-width: 150px;'
            'id': 'id_difficulty_ce_generator' # ID para o JS do template
            })
    )
    area = forms.ModelChoiceField(
        queryset=AreaConhecimento.objects.all().order_by('nome'),
        label="Área de Conhecimento", # Alterado para refletir que é para categorizar as novas questões
        required=True, # Definido como True, pois novas questões geralmente precisam de uma área
        empty_label="-- Selecione a Área --", # Rótulo vazio mais informativo
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm', # Aplicando form-select-sm
            # 'style': 'max-width: 200px;'
            'id': 'id_area_ce_generator' # ID para o JS do template
            }),
        help_text="Selecione a área para as novas questões geradas." # Help text ajustado
    )

    def __init__(self, *args, **kwargs):
        max_questions_limit = kwargs.pop('max_questions', getattr(settings, 'AI_MAX_QUESTIONS_PER_REQUEST', 10))
        super().__init__(*args, **kwargs)
        
        # Ajusta o campo num_questions (lógica existente mantida)
        if 'num_questions' in self.fields: # Boa prática verificar se o campo existe
            self.fields['num_questions'].max_value = max_questions_limit
            self.fields['num_questions'].widget.attrs['max'] = max_questions_limit
            # O min_value já está definido no campo, então podemos usá-lo no help_text
            min_val = self.fields['num_questions'].min_value or 1 
            self.fields['num_questions'].help_text = f"Gere entre {min_val} e {max_questions_limit}."

    def clean_topic(self):
        topic = self.cleaned_data.get('topic', '').strip()
        
        # Esta validação de comprimento só será efetivamente um problema se o 'topic'
        # for a única fonte de contexto e o usuário digitar algo muito curto.
        # Se um PDF for enviado e o 'topic' estiver vazio, a view deve ter tornado
        # este campo opcional, então cleaned_data.get('topic') será vazio e este 'if topic' não será True.
        if topic and len(topic) < 4:
            raise ValidationError("Tópico/Contexto textual fornecido é muito curto (mínimo de 4 caracteres).")
        return topic

    def clean_num_questions(self):
        # Sua lógica existente para clean_num_questions está boa.
        num = self.cleaned_data.get('num_questions')
        if num is not None:
            max_limit = self.fields['num_questions'].max_value
            min_limit = self.fields['num_questions'].min_value
            if min_limit is not None and num < min_limit:
                raise ValidationError(f"O número mínimo de questões é {min_limit}.")
            if max_limit is not None and num > max_limit:
                raise ValidationError(f"O número máximo de questões é {max_limit}.")
        return num

    # --- NOVO MÉTODO clean() PARA VALIDAÇÃO CRUZADA ---
    def clean(self):
        cleaned_data = super().clean()
        topic = cleaned_data.get('topic', '').strip()
        pdf_contexto = cleaned_data.get('pdf_contexto') # Este é o UploadedFile object ou None

        # A view (generate_questions_view) DEVE ter ajustado self.fields['topic'].required = False
        # se um PDF foi detectado em request.FILES, ANTES de form.is_valid() ser chamado.

        # Esta validação garante que PELO MENOS UM (tópico ou PDF) foi fornecido.
        if not topic and not pdf_contexto:
            # Se a view não ajustou topic.required e o topic estava vazio, Django já teria
            # adicionado um erro a 'topic'. Este erro aqui é mais geral ou para 'pdf_contexto'.
            # Para evitar mensagens duplicadas, podemos ser mais específicos.
            
            # Se 'topic' era obrigatório (nenhum PDF enviado) e está vazio, Django já tratou.
            # Este 'raise' é para o caso em que 'topic' se tornou opcional (devido ao PDF),
            # mas o PDF também não foi enviado (ex: usuário limpou o campo PDF após selecioná-lo).
            # Ou para o caso em que 'topic' era opcional por padrão.
            
            # No nosso caso, 'topic' começa como required=True. A view o torna False se há PDF.
            # Se não há PDF, 'topic' permanece required=True. Se estiver vazio, o erro já existe.
            # Se há PDF, 'topic' se torna required=False. Se estiver vazio, tudo bem.
            # O que este clean() realmente precisa garantir é que, se 'topic' está vazio E 'pdf_contexto' está vazio,
            # então um erro deve ser lançado *se ainda não houver um erro 'required' no 'topic'*.

            if not self.errors.get('topic'): # Só adiciona erro se o 'topic' não tiver já um erro de 'required'
                error_message = "Forneça um Tópico/Contexto textual OU envie um arquivo PDF."
                # Adicionar a ambos para que o usuário veja onde a ação é necessária
                self.add_error('topic', ValidationError(error_message, code='input_required'))
                self.add_error('pdf_contexto', ValidationError(error_message, code='input_required'))
                # Ou um erro não vinculado:
                # raise ValidationError(error_message, code='input_required')

        return cleaned_data
    
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
    
    # --- NOVO FORMULÁRIO: Pergunte à IA ---
class AskAIForm(forms.Form):
    user_question = forms.CharField(
        label="Sua Pergunta",
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Digite sua pergunta ou comando para a IA...',
            'class': 'form-control'
        }),
        required=True,
        help_text="Seja claro e específico na sua pergunta."
    )

# --- NOVO FORMULÁRIO: Adicionar/Editar Área de Conhecimento ---
class AreaConhecimentoForm(forms.ModelForm):
    class Meta:
        model = AreaConhecimento
        fields = ['nome'] # Apenas o campo 'nome' será editável pelo usuário
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control form-control-lg', # Input maior
                'placeholder': 'Ex: Direito Administrativo'
            })
        }
        labels = {
            'nome': 'Nome da Nova Área de Conhecimento', # Label mais descritivo
        }
        help_texts = {
            'nome': 'O nome deve ser único.',
        }

    def clean_nome(self):
        nome = self.cleaned_data.get('nome')
        if nome:
            # Verifica se já existe uma área com o mesmo nome (ignorando maiúsculas/minúsculas)
            # Exclui o próprio objeto se estiver a editar (instance.pk existe)
            query = AreaConhecimento.objects.filter(nome__iexact=nome)
            if self.instance and self.instance.pk:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise ValidationError("Já existe uma Área de Conhecimento com este nome.")
        return nome
# --- FIM NOVO FORMULÁRIO ---


    def clean_user_question(self):
        question = self.cleaned_data.get('user_question', '').strip()
        if len(question) < 5:
            raise ValidationError("Sua pergunta parece muito curta. Tente ser mais específico.")
        # Adicionar outras validações se necessário
        return question
# --- FIM NOVO FORMULÁRIO ---
class PDFUploadForm(forms.Form):
    pdf_file = forms.FileField(
        label='Selecione o arquivo PDF',
        help_text='Máximo de 50MB. Apenas arquivos .pdf são permitidos.',
        widget=forms.ClearableFileInput(attrs={'accept': '.pdf', 'class': 'form-control'})
    )
    num_questions_ce = forms.IntegerField(
        label='Número de Questões Certo/Errado',
        min_value=0, 
        max_value=20,
        initial=5,
        required=False,
        help_text='Deixe em 0 ou em branco se não desejar questões C/E.',
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    num_aspects_discursive = forms.IntegerField(
        label='Número de Aspectos para Questão Discursiva',
        min_value=0, 
        max_value=5,
        initial=3,
        required=False,
        help_text='Deixe em 0 ou em branco se não desejar questão discursiva.',
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    difficulty_level = forms.ChoiceField(
        label='Nível de Dificuldade',
        choices=[
            ('facil', 'Fácil'),
            ('medio', 'Médio'),
            ('dificil', 'Difícil')
        ],
        initial='medio',
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    area = forms.ModelChoiceField(
        queryset=AreaConhecimento.objects.all().order_by('nome'), 
        required=False, 
        label="Área de Conhecimento (Opcional)",
        help_text="Selecione uma área para associar às questões geradas.",
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="-- Nenhuma Área Específica --" 
    )

    def clean_pdf_file(self):
        file = self.cleaned_data.get('pdf_file')
        if file:
            if file.content_type != 'application/pdf':
                raise forms.ValidationError('Arquivo inválido. Por favor, envie um arquivo PDF.')
            if file.size > 50 * 1024 * 1024: # Limite de 50MB
                raise forms.ValidationError('Arquivo muito grande. O limite é de 50MB.')
        return file

    def clean_num_questions_ce(self):
        num = self.cleaned_data.get('num_questions_ce')
        if num is None: 
            return 0
        return num

    def clean_num_aspects_discursive(self):
        num = self.cleaned_data.get('num_aspects_discursive')
        if num is None: 
            return 0
        return num
