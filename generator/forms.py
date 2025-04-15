# generator/forms.py
from django import forms
from django.conf import settings

class QuestionGeneratorForm(forms.Form):
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

    def __init__(self, *args, **kwargs):
        max_questions_limit = kwargs.pop('max_questions', settings.AI_MAX_QUESTIONS_PER_REQUEST)
        super().__init__(*args, **kwargs)

        self.fields['num_questions'].max_value = max_questions_limit
        self.fields['num_questions'].widget.attrs['max'] = max_questions_limit
        self.fields['num_questions'].help_text = f"Gere entre 1 e {max_questions_limit} questões por vez."

    def clean_topic(self):
        topic = self.cleaned_data.get('topic', '').strip()

        if len(topic) < 10:
            raise forms.ValidationError("Descreva o tópico com mais detalhes (mínimo 10 caracteres).")

        # Tópicos genéricos demais que causam problemas frequentes
        generic_topics = ['redes de computadores', 'direito', 'filosofia', 'história']
        if topic.lower() in generic_topics:
            raise forms.ValidationError("Tente ser mais específico. Por exemplo, em vez de 'redes de computadores', use 'Modelo OSI' ou 'Protocolos TCP/IP'.")

        return topic

    def clean_num_questions(self):
        num = self.cleaned_data.get('num_questions')
        max_limit = settings.AI_MAX_QUESTIONS_PER_REQUEST

        if num is not None and num > max_limit:
            raise forms.ValidationError(f"O número máximo de questões permitido é {max_limit}.")

        return num
