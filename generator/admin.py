# generator/admin.py
from django.contrib import admin
from .models import AreaConhecimento, Questao, TentativaResposta, Avaliacao
from .models import OrgaoPCI, BancaPCI, NivelEscolaridadePCI, CargoPCI, ProvaPCIConcurso # e outros modelos

# Registra os models para que apareçam na interface de administração

@admin.register(AreaConhecimento)
class AreaConhecimentoAdmin(admin.ModelAdmin):
    list_display = ('nome',) # Colunas a exibir na lista
    search_fields = ('nome',) # Campo para busca

@admin.register(Questao)
class QuestaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'tipo', 'area', 'dificuldade', 'criado_por', 'criado_em')
    list_filter = ('tipo', 'dificuldade', 'area', 'criado_por') # Filtros laterais
    search_fields = ('texto_comando', 'texto_motivador', 'aspectos_discursiva')
    raw_id_fields = ('area', 'criado_por') # Melhor para chaves estrangeiras com muitos itens

@admin.register(TentativaResposta)
class TentativaRespostaAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'questao_link', 'data_resposta', 'resposta_ce')
    list_filter = ('usuario', 'questao__tipo', 'data_resposta')
    search_fields = ('resposta_discursiva',)
    raw_id_fields = ('usuario', 'questao') # Melhor para performance

    # Link para a questão na lista
    def questao_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        link = reverse("admin:generator_questao_change", args=[obj.questao.id]) # Assumindo app_label 'generator'
        return format_html('<a href="{}">Questão #{}</a>', link, obj.questao.id)
    questao_link.short_description = 'Questão'

@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ('tentativa_id', 'usuario', 'questao_tipo', 'correto_ce', 'score_ce', 'npd', 'data_avaliacao')
    list_filter = ('tentativa__questao__tipo', 'correto_ce')
    raw_id_fields = ('tentativa',) # Campo OneToOne é a chave primária

    # Métodos para mostrar info da tentativa relacionada
    def usuario(self, obj):
        return obj.tentativa.usuario
    usuario.short_description = 'Usuário'

    def questao_tipo(self, obj):
         return obj.tentativa.questao.get_tipo_display()
    questao_tipo.short_description = 'Tipo Questão'
    
# generator/admin.py

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

@admin.register(ProvaPCIConcurso)
class ProvaPCIConcursoAdmin(admin.ModelAdmin):
    list_display = ('nome_concurso_detalhado', 'orgao', 'cargo', 'banca', 'ano', 'nivel_escolaridade', 'data_coleta')
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