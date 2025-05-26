# generator/admin.py
from django.contrib import admin
from .models import (
    AreaConhecimento, Questao, TentativaResposta, Avaliacao, PalavraChave, # Adicionado PalavraChave que estava faltando no import original
    OrgaoPCI, BancaPCI, NivelEscolaridadePCI, CargoPCI, ProvaPCIConcurso,
    # --- Importar os novos modelos para Leis do Planalto ---
    TipoNormaPlanalto, LeiPlanalto, Topico
)

# Registra os models para que apareçam na interface de administração

@admin.register(AreaConhecimento)
class AreaConhecimentoAdmin(admin.ModelAdmin):
    list_display = ('nome',) # Colunas a exibir na lista
    search_fields = ('nome',) # Campo para busca

@admin.register(Topico) # Importar Topico se ele for registrado aqui. Parece que Topico não estava sendo registrado.
class TopicoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'area_conhecimento')
    search_fields = ('nome',)
    list_filter = ('area_conhecimento',)

@admin.register(Questao)
class QuestaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'tipo', 'area', 'topico', 'dificuldade', 'criado_por', 'criado_em') # Adicionado topico
    list_filter = ('tipo', 'dificuldade', 'area', 'criado_por', 'topico') # Adicionado topico
    search_fields = ('texto_comando', 'texto_motivador', 'aspectos_discursiva')
    raw_id_fields = ('area', 'topico', 'criado_por') # Adicionado topico

@admin.register(TentativaResposta)
class TentativaRespostaAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'questao_link', 'data_resposta', 'resposta_ce')
    list_filter = ('usuario', 'questao__tipo', 'data_resposta')
    search_fields = ('resposta_discursiva',)
    raw_id_fields = ('usuario', 'questao')

    def questao_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        link = reverse("admin:generator_questao_change", args=[obj.questao.id])
        return format_html('<a href="{}">Questão #{}</a>', link, obj.questao.id)
    questao_link.short_description = 'Questão'

@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ('tentativa_id', 'usuario', 'questao_tipo', 'correto_ce', 'score_ce', 'npd', 'data_avaliacao')
    list_filter = ('tentativa__questao__tipo', 'correto_ce')
    raw_id_fields = ('tentativa',)

    def usuario(self, obj):
        return obj.tentativa.usuario
    usuario.short_description = 'Usuário'

    def questao_tipo(self, obj):
         return obj.tentativa.questao.get_tipo_display()
    questao_tipo.short_description = 'Tipo Questão'

@admin.register(PalavraChave)
class PalavraChaveAdmin(admin.ModelAdmin):
    list_display = ('texto', 'criado_em', 'atualizado_em')
    search_fields = ('texto',)

# --- Modelos do PCI Concursos ---
@admin.register(OrgaoPCI)
class OrgaoPCIAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)

@admin.register(BancaPCI)
class BancaPCIAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)

@admin.register(NivelEscolaridadePCI)
class NivelEscolaridadePCIAdmin(admin.ModelAdmin):
    list_display = ('nome',)

@admin.register(CargoPCI)
class CargoPCIAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)
    # Se você adicionar um campo de categoria ao CargoPCI, adicione-o ao list_filter também.

@admin.register(ProvaPCIConcurso)
class ProvaPCIConcursoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome_concurso_detalhado', 'orgao', 'cargo', 'banca', 'ano', 'nivel_escolaridade', 'data_coleta')
    list_filter = ('ano', 'orgao', 'banca', 'nivel_escolaridade', 'data_coleta')
    search_fields = ('nome_concurso_detalhado', 'orgao__nome', 'cargo__nome', 'banca__nome', 'url_pagina_detalhes')
    readonly_fields = ('data_coleta', 'data_atualizacao_coleta')
    fieldsets = (
        (None, {
            'fields': ('titulo_link_origem', 'nome_concurso_detalhado', 'url_pagina_detalhes', 'fonte')
        }),
        ('Detalhes do Concurso', {
            'fields': ('orgao', 'cargo', 'banca', 'ano', 'nivel_escolaridade', 'categoria_cargo_principal_texto')
        }),
        ('Arquivos', {
            'fields': ('url_prova_pdf', 'url_gabarito_pdf')
        }),
        ('Datas de Controle', {
            'fields': ('data_coleta', 'data_atualizacao_coleta')
        }),
    )

# --- NOVOS MODELOS PARA LEIS DO PLANALTO ---
@admin.register(TipoNormaPlanalto)
class TipoNormaPlanaltoAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)
    ordering = ['nome']

@admin.register(LeiPlanalto)
class LeiPlanaltoAdmin(admin.ModelAdmin):
    list_display = ('id','get_tipo_norma_nome', 'numero_norma', 'ano_norma', 'data_publicacao', 'get_titulo_curto', 'url_original', 'data_coleta')
    list_filter = ('tipo_norma', 'ano_norma', 'data_publicacao')
    search_fields = ('titulo_ou_ementa', 'numero_norma', 'texto_integral_html', 'url_original')
    readonly_fields = ('data_coleta', 'ultima_verificacao_coleta')
    list_per_page = 25

    fieldsets = (
        ('Identificação da Norma', {
            'fields': ('url_original', 'tipo_norma', 'numero_norma', 'ano_norma', 'data_publicacao')
        }),
        ('Conteúdo', {
            'fields': ('titulo_ou_ementa', 'texto_integral_html')
        }),
        ('Metadados da Coleta', {
            'fields': ('data_coleta', 'ultima_verificacao_coleta')
        }),
    )

    def get_titulo_curto(self, obj):
        if obj.titulo_ou_ementa:
            return (obj.titulo_ou_ementa[:75] + '...') if len(obj.titulo_ou_ementa) > 75 else obj.titulo_ou_ementa
        return "N/A"
    get_titulo_curto.short_description = 'Título/Ementa'

    def get_tipo_norma_nome(self, obj):
        if obj.tipo_norma:
            return obj.tipo_norma.nome
        return "N/A"
    get_tipo_norma_nome.short_description = 'Tipo'
    get_tipo_norma_nome.admin_order_field = 'tipo_norma__nome' # Permite ordenar por este campo