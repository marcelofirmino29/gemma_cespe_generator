# generator/models.py
from django.db import models
from django.conf import settings # Para referenciar o User padrão do Django
from django.utils import timezone # Para timestamps

# Modelo para Categorização (Opcional, mas útil)
class AreaConhecimento(models.Model):
    nome = models.CharField(max_length=150, unique=True, verbose_name="Nome da Área")
    # Você pode adicionar mais campos, como uma descrição ou área pai

    class Meta:
        verbose_name = "Área de Conhecimento"
        verbose_name_plural = "Áreas de Conhecimento"
        ordering = ['nome'] # Ordena alfabeticamente por padrão

    def __str__(self):
        return self.nome

# Modelo para armazenar os Tópicos
class Topico(models.Model):
    nome = models.CharField(max_length=150, unique=True, verbose_name="Nome do Tópico")
    area_conhecimento = models.ForeignKey(
        AreaConhecimento,
        on_delete=models.CASCADE,
        verbose_name="Área de Conhecimento"
    )

    class Meta:
        verbose_name = "Tópico"
        verbose_name_plural = "Tópicos"
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.area_conhecimento.nome})"

# Modelo para armazenar as Questões Geradas
class Questao(models.Model):
    TIPO_QUESTAO_CHOICES = [
        ('CE', 'Certo/Errado'),
        ('DISC', 'Discursiva'),
    ]
    DIFICULDADE_CHOICES = [
        ('facil', 'Fácil'),
        ('medio', 'Médio'),
        ('dificil', 'Difícil'),
    ]

    area = models.ForeignKey(
        AreaConhecimento,
        on_delete=models.SET_NULL, # Se a área for deletada, o campo fica nulo
        null=True, blank=True,      # Permite que a área seja opcional
        verbose_name="Área de Conhecimento"
    )
    topico = models.ForeignKey(
        Topico,
        on_delete=models.SET_NULL, # Se o tópico for deletado, o campo fica nulo
        null=True, blank=True,      # Permite que o tópico seja opcional
        verbose_name="Tópico"
    )
    tipo = models.CharField(
        max_length=4,
        choices=TIPO_QUESTAO_CHOICES,
        verbose_name="Tipo de Questão"
    )
    dificuldade = models.CharField(
        max_length=15,
        choices=DIFICULDADE_CHOICES,
        default='medio',
        blank=True, # Pode ser opcional
        verbose_name="Nível de Dificuldade"
    )
    texto_motivador = models.TextField(
        null=True, blank=True,
        verbose_name="Texto Motivador (Discursiva)"
    )
    texto_comando = models.TextField(
        verbose_name="Texto da Afirmação (C/E) ou Comando (Discursiva)"
    )
    aspectos_discursiva = models.TextField(
        null=True, blank=True,
        verbose_name="Aspectos a Avaliar (Discursiva)",
        help_text="Liste os pontos que a resposta discursiva deve cobrir."
    )
    gabarito_ce = models.CharField(
        max_length=1,
        choices=[('C','Certo'), ('E','Errado')],
        null=True, blank=True, # Só aplicável para C/E
        verbose_name="Gabarito Certo/Errado"
    )
    justificativa_gabarito = models.TextField(
        null=True, blank=True,
        verbose_name="Justificativa do Gabarito (C/E)",
        help_text="Explicação do porquê a afirmação C/E é certa ou errada."
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # Se usuário for deletado, questão fica sem criador mas não é deletada
        null=True,                 # Permite valor nulo no DB
        blank=True,                # Permite campo vazio em forms/admin
        verbose_name="Criado por"
    )

    class Meta:
        verbose_name = "Questão"
        verbose_name_plural = "Questões"
        ordering = ['-criado_em'] # Mais recentes primeiro

    def __str__(self):
        tipo_str = self.get_tipo_display()
        return f"[{tipo_str}] {self.texto_comando[:80]}..."

# Modelo para armazenar as tentativas de resposta do usuário
class TentativaResposta(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Usuário")
    questao = models.ForeignKey(Questao, on_delete=models.CASCADE, verbose_name="Questão Respondida")
    resposta_ce = models.CharField(max_length=1, choices=[('C','Certo'), ('E','Errado')], null=True, blank=True, verbose_name="Resposta C/E")
    resposta_discursiva = models.TextField(null=True, blank=True, verbose_name="Resposta Discursiva")
    data_resposta = models.DateTimeField(default=timezone.now, verbose_name="Data da Resposta")
    class Meta: verbose_name = "Tentativa de Resposta"; verbose_name_plural = "Tentativas de Respostas"; ordering = ['-data_resposta']
    def __str__(self): return f"Tentativa de {self.usuario.username} para Questão #{self.questao.id}"

# Modelo para armazenar o resultado da avaliação/validação
class Avaliacao(models.Model):
    tentativa = models.OneToOneField(TentativaResposta, on_delete=models.CASCADE, primary_key=True, verbose_name="Tentativa Avaliada")
    correto_ce = models.BooleanField(null=True, verbose_name="Acertou C/E?")
    score_ce = models.IntegerField(null=True, verbose_name="Score C/E (+1/-1)")
    nc = models.FloatField(null=True, verbose_name="Nota Conteúdo (NC)")
    ne = models.IntegerField(null=True, verbose_name="Contagem Erros (NE)")
    npd = models.FloatField(null=True, verbose_name="Nota Final (NPD)")
    feedback_ai = models.TextField(null=True, blank=True, verbose_name="Feedback Bruto AI")
    justificativa_nc_ai = models.TextField(null=True, blank=True, verbose_name="Justificativa NC (Parseada)")
    comentarios_ai = models.TextField(null=True, blank=True, verbose_name="Comentários AI (Parseado)")
    data_avaliacao = models.DateTimeField(auto_now_add=True, verbose_name="Data da Avaliação")
    class Meta: verbose_name = "Avaliação"; verbose_name_plural = "Avaliações"
    def __str__(self): return f"Avaliação da Tentativa #{self.tentativa.id} por {self.tentativa.usuario.username}"


class PalavraChave(models.Model):
    """
    Modelo para armazenar palavras-chave ou tópicos para a nuvem de palavras.
    """
    texto = models.CharField(
        max_length=100,
        unique=True, # Garante que cada palavra seja única
        verbose_name="Palavra/Tópico"
    )
    # Opcional: Adicionar um campo de frequência se quiser controlar o tamanho na nuvem
    # frequencia = models.PositiveIntegerField(default=1, verbose_name="Frequência")
    # Opcional: Adicionar data de criação/atualização
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.texto

    class Meta:
        verbose_name = "Palavra-chave"
        verbose_name_plural = "Palavras-chave"
        ordering = ['texto'] # Ordena alfabeticamente por padrão
        
class OrgaoPCI(models.Model):
    nome = models.CharField(max_length=255, unique=True)
    # outros campos se necessário
    def __str__(self):
        return self.nome

class BancaPCI(models.Model):
    nome = models.CharField(max_length=255, unique=True)
    # outros campos
    def __str__(self):
        return self.nome

class NivelEscolaridadePCI(models.Model):
    nome = models.CharField(max_length=100, unique=True) # Fundamental, Médio, Superior
    def __str__(self):
        return self.nome

class CargoPCI(models.Model):
    nome = models.CharField(max_length=255)
    # idealmente, normalizar mais, mas para começar:
    # categoria_principal = models.CharField(max_length=255, null=True, blank=True) 
    def __str__(self):
        return self.nome
    # Pode ter uma ForeignKey para uma CategoriaPCI mais tarde

class ProvaPCIConcurso(models.Model):
    titulo_link_origem = models.CharField(max_length=500, blank=True, null=True)
    nome_concurso_detalhado = models.CharField(max_length=500, blank=True, null=True)

    orgao = models.ForeignKey(OrgaoPCI, on_delete=models.SET_NULL, null=True, blank=True)
    cargo = models.ForeignKey(CargoPCI, on_delete=models.SET_NULL, null=True, blank=True) # Ou ManyToManyField se uma prova pode ter múltiplos cargos
    # cargo_detalhado_texto = models.CharField(max_length=500, blank=True, null=True) # Para o texto bruto se necessário

    banca = models.ForeignKey(BancaPCI, on_delete=models.SET_NULL, null=True, blank=True)
    ano = models.IntegerField(null=True, blank=True)
    nivel_escolaridade = models.ForeignKey(NivelEscolaridadePCI, on_delete=models.SET_NULL, null=True, blank=True)
    nivel_detalhado_texto = models.CharField(max_length=100, blank=True, null=True)

    url_pagina_detalhes = models.URLField(max_length=1024, unique=True)
    url_prova_pdf = models.URLField(max_length=1024, null=True, blank=True)
    url_gabarito_pdf = models.URLField(max_length=1024, null=True, blank=True)

    fonte = models.CharField(max_length=100, default="PCI Concursos")
    categoria_cargo_principal_texto = models.CharField(max_length=255, blank=True, null=True) # Texto da categoria original

    data_coleta = models.DateTimeField(auto_now_add=True)
    data_atualizacao_coleta = models.DateTimeField(auto_now=True)

    # Opcional: link para o modelo Questao se você for extrair questões dos PDFs
    # questoes = models.ManyToManyField('Questao', blank=True)

    class Meta:
        verbose_name = "Prova Coletada (PCI)"
        verbose_name_plural = "Provas Coletadas (PCI)"
        ordering = ['-ano', 'orgao__nome']

    def __str__(self):
        return f"{self.orgao} - {self.cargo} ({self.ano})"