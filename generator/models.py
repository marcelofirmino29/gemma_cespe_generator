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
        # Removido unique_together se não for estritamente necessário e puder causar conflitos
        # unique_together = ('nome', 'area_conhecimento') # Garante que a combinação de nome e área seja única

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
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Área de Conhecimento"
    )
    topico = models.ForeignKey(
        Topico,
        on_delete=models.SET_NULL,
        null=True, blank=True,
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
        blank=True,
        verbose_name="Nível de Dificuldade"
    )
    texto_motivador = models.TextField(
        null=True, blank=True,
        verbose_name="Texto Motivador (Discursiva)"
    )
    texto_comando = models.TextField( # Este campo foi removido em uma migração anterior, mas está no seu admin.py. Decida se ele deve existir.
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
        null=True, blank=True,
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
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Criado por"
    )

    # Campos que parecem ter sido adicionados pela migração 0006 e 0007
    # Certifique-se de que eles correspondem ao seu estado atual do banco de dados
    # Se 'texto_comando' foi realmente removido, remova-o daqui também.
    # Se 'enunciado_principal' e 'item_julgamento' foram adicionados, adicione-os.
    # Exemplo (baseado na migração 0006):
    # enunciado_principal = models.TextField(verbose_name="Enunciado Principal (Contexto)", blank=True, null=True)
    # item_julgamento = models.TextField(verbose_name="Item para Julgamento (Afirmação C/E)", blank=True, null=True)


    class Meta:
        verbose_name = "Questão"
        verbose_name_plural = "Questões"
        ordering = ['-criado_em']

    def __str__(self):
        tipo_str = self.get_tipo_display()
        # Ajuste para usar item_julgamento ou texto_comando dependendo do seu modelo final
        texto_base = self.texto_comando # ou self.item_julgamento
        return f"[{tipo_str}] {texto_base[:80]}..." if texto_base else f"[{tipo_str}] Questão ID {self.id}"

class TentativaResposta(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Usuário")
    questao = models.ForeignKey(Questao, on_delete=models.CASCADE, verbose_name="Questão Respondida")
    resposta_ce = models.CharField(max_length=1, choices=[('C','Certo'), ('E','Errado')], null=True, blank=True, verbose_name="Resposta C/E")
    resposta_discursiva = models.TextField(null=True, blank=True, verbose_name="Resposta Discursiva")
    data_resposta = models.DateTimeField(default=timezone.now, verbose_name="Data da Resposta")
    class Meta:
        verbose_name = "Tentativa de Resposta"
        verbose_name_plural = "Tentativas de Respostas"
        ordering = ['-data_resposta']
    def __str__(self): return f"Tentativa de {self.usuario.username} para Questão #{self.questao.id}"

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
    class Meta:
        verbose_name = "Avaliação"
        verbose_name_plural = "Avaliações"
    def __str__(self): return f"Avaliação da Tentativa #{self.tentativa.id} por {self.tentativa.usuario.username}"

class PalavraChave(models.Model):
    texto = models.CharField(max_length=100, unique=True, verbose_name="Palavra/Tópico")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    def __str__(self): return self.texto
    class Meta:
        verbose_name = "Palavra-chave"
        verbose_name_plural = "Palavras-chave"
        ordering = ['texto']

# --- Modelos para Scraper PCI Concursos (PROVAS) ---
class OrgaoPCI(models.Model):
    nome = models.CharField(max_length=255, unique=True)
    def __str__(self): return self.nome
    class Meta: verbose_name = "Órgão (PCI)"

class BancaPCI(models.Model):
    nome = models.CharField(max_length=255, unique=True)
    def __str__(self): return self.nome
    class Meta: verbose_name = "Banca (PCI)"

class NivelEscolaridadePCI(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.nome
    class Meta: verbose_name = "Nível Escolaridade (PCI)"

class CargoPCI(models.Model):
    nome = models.CharField(max_length=255, unique=True) # Adicionado unique=True
    def __str__(self): return self.nome
    class Meta: verbose_name = "Cargo (PCI)"

class ProvaPCIConcurso(models.Model):
    titulo_link_origem = models.CharField(max_length=500, blank=True, null=True)
    nome_concurso_detalhado = models.CharField(max_length=500, blank=True, null=True)
    orgao = models.ForeignKey(OrgaoPCI, on_delete=models.SET_NULL, null=True, blank=True)
    cargo = models.ForeignKey(CargoPCI, on_delete=models.SET_NULL, null=True, blank=True)
    banca = models.ForeignKey(BancaPCI, on_delete=models.SET_NULL, null=True, blank=True)
    ano = models.IntegerField(null=True, blank=True)
    nivel_escolaridade = models.ForeignKey(NivelEscolaridadePCI, on_delete=models.SET_NULL, null=True, blank=True)
    nivel_detalhado_texto = models.CharField(max_length=100, blank=True, null=True)
    url_pagina_detalhes = models.URLField(max_length=1024, unique=True)
    url_prova_pdf = models.URLField(max_length=1024, null=True, blank=True)
    url_gabarito_pdf = models.URLField(max_length=1024, null=True, blank=True)
    fonte = models.CharField(max_length=100, default="PCI Concursos")
    categoria_cargo_principal_texto = models.CharField(max_length=255, blank=True, null=True)
    data_coleta = models.DateTimeField(auto_now_add=True)
    data_atualizacao_coleta = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = "Prova Coletada (PCI)"
        verbose_name_plural = "Provas Coletadas (PCI)"
        ordering = ['-ano', 'orgao__nome']
    def __str__(self):
        return f"{self.nome_concurso_detalhado or self.titulo_link_origem or 'Prova ID ' + str(self.id)}"

# --- NOVOS MODELOS PARA LEIS DO PLANALTO ---
class TipoNormaPlanalto(models.Model):
    nome = models.CharField(max_length=100, unique=True, help_text="Ex: Lei, Decreto, Lei Complementar, Medida Provisória")
    def __str__(self): return self.nome
    class Meta:
        verbose_name = "Tipo de Norma (Planalto)"
        verbose_name_plural = "Tipos de Normas (Planalto)"
        ordering = ['nome']

class LeiPlanalto(models.Model):
    titulo_ou_ementa = models.TextField(blank=True, null=True, help_text="Título completo ou ementa da norma.")
    numero_norma = models.CharField(max_length=100, blank=True, null=True, help_text="Número da lei, decreto, etc. Ex: 14.133")
    ano_norma = models.IntegerField(blank=True, null=True, help_text="Ano de publicação da norma. Ex: 2021")
    tipo_norma = models.ForeignKey(TipoNormaPlanalto, on_delete=models.SET_NULL, null=True, blank=True, help_text="Tipo da norma (Lei, Decreto, etc.)")
    data_publicacao = models.DateField(blank=True, null=True, help_text="Data de assinatura ou publicação da norma.")
    url_original = models.URLField(max_length=1024, unique=True, help_text="URL única da norma no site do Planalto.")
    texto_integral_html = models.TextField(blank=True, null=True, help_text="Conteúdo HTML da lei, se capturado.")
    data_coleta = models.DateTimeField(auto_now_add=True)
    ultima_verificacao_coleta = models.DateTimeField(default=timezone.now)
    class Meta:
        verbose_name = "Lei do Planalto Coletada"
        verbose_name_plural = "Leis do Planalto Coletadas"
        ordering = ['-ano_norma', '-data_publicacao', 'numero_norma']
        indexes = [
            models.Index(fields=['tipo_norma', 'ano_norma', 'numero_norma']),
            models.Index(fields=['url_original']),
        ]
    def __str__(self):
        parts = []
        if self.tipo_norma: parts.append(str(self.tipo_norma))
        if self.numero_norma: parts.append(f"nº {self.numero_norma}")
        if self.ano_norma: parts.append(f"/{self.ano_norma}")
        if not parts and self.titulo_ou_ementa: return f"{self.titulo_ou_ementa[:70]}..."
        if not parts: return self.url_original
        return " ".join(parts)

# --- MODELOS PARA O SCRAPER CONCURSOSNOBRASIL.COM ---
class ConcursoNoBrasil(models.Model):
    organizacao = models.CharField(max_length=300)
    vagas_disponiveis = models.CharField(max_length=100, blank=True, null=True)
    link = models.URLField(max_length=1000, unique=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    categoria_coleta = models.CharField(max_length=10, blank=True, null=True, help_text="UF ou 'br' da coleta")
    data_coleta = models.DateTimeField(auto_now_add=True)
    ultima_atualizacao_coleta = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Concurso (ConcursosNoBrasil)"
        verbose_name_plural = "Concursos (ConcursosNoBrasil)"
        ordering = ['-data_coleta', 'organizacao']
        indexes = [
            models.Index(fields=['link']),
            models.Index(fields=['status', 'categoria_coleta']),
        ]
    def __str__(self):
        return f"{self.organizacao} ({self.status or 'N/A'}) - Vagas: {self.vagas_disponiveis or 'N/A'}"

# --- MODELOS PARA O SCRAPER DE NOTÍCIAS DA CAPA DO PCI CONCURSOS ---
class NoticiaPCICapa(models.Model):
    titulo = models.CharField(max_length=500)
    link_detalhes = models.URLField(max_length=1000, unique=True)
    vagas_disponiveis = models.CharField(max_length=100, blank=True, null=True)
    resumo = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    # Não temos estado/região na capa de forma confiável
    data_coleta = models.DateTimeField(auto_now_add=True)
    ultima_atualizacao_coleta = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Notícia da Capa (PCI)"
        verbose_name_plural = "Notícias da Capa (PCI)"
        ordering = ['-data_coleta']
        indexes = [
            models.Index(fields=['link_detalhes']),
        ]
    def __str__(self):
        return f"{self.titulo} ({self.status or 'N/A'})"

