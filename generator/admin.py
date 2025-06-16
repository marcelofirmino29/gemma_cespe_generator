from django.contrib import admin
from .models import (
    AreaConhecimento, Topico, Questao, TentativaResposta, Avaliacao,
    KahootGame, KahootPlayer, PalavraChave, OrgaoPCI, BancaPCI,
    NivelEscolaridadePCI, CargoPCI, ProvaPCIConcurso, TipoNormaPlanalto,
    LeiPlanalto, ConcursoNoBrasil, NoticiaPCICapa, Organizacao, StatusConcurso
)

# Registrando os modelos principais
@admin.register(AreaConhecimento)
class AreaConhecimentoAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)

@admin.register(Topico)
class TopicoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'area_conhecimento')
    list_filter = ('area_conhecimento',)
    search_fields = ('nome', 'area_conhecimento__nome')
    raw_id_fields = ('area_conhecimento',)

@admin.register(Questao)
class QuestaoAdmin(admin.ModelAdmin):
    # --- CONFIGURAÇÃO CORRIGIDA ---
    # 'area' foi removido de list_display e substituído por um método.
    list_display = ('id', 'tipo', 'get_area', 'topico', 'dificuldade', 'criado_em', 'gerada_por_ia_para_jogo')
    # 'area' foi removido de list_filter e substituído pelo relacionamento correto.
    list_filter = ('tipo', 'dificuldade', 'topico__area_conhecimento', 'gerada_por_ia_para_jogo')
    search_fields = ('enunciado', 'topico__nome', 'topico__area_conhecimento__nome')
    # 'area' foi removido de raw_id_fields.
    raw_id_fields = ('topico', 'criado_por')
    list_per_page = 20

    @admin.display(description='Área de Conhecimento', ordering='topico__area_conhecimento__nome')
    def get_area(self, obj):
        """Método para exibir a Área de Conhecimento através do Tópico."""
        if obj.topico and obj.topico.area_conhecimento:
            return obj.topico.area_conhecimento.nome
        return "N/A"

@admin.register(TentativaResposta)
class TentativaRespostaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'questao', 'data_resposta')
    list_filter = ('usuario',)
    search_fields = ('usuario__username', 'questao__enunciado')
    raw_id_fields = ('usuario', 'questao')

@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ('tentativa', 'correto_ce', 'npd', 'data_avaliacao')
    list_filter = ('correto_ce',)
    raw_id_fields = ('tentativa',)

# Registrando os modelos de Jogos
@admin.register(KahootGame)
class KahootGameAdmin(admin.ModelAdmin):
    list_display = ('pin', 'topico_descritivo', 'host', 'status', 'created_at')
    list_filter = ('status', 'host')
    search_fields = ('pin', 'host__username', 'topico_descritivo__nome')
    raw_id_fields = ('topico_descritivo', 'host', 'questoes')

@admin.register(KahootPlayer)
class KahootPlayerAdmin(admin.ModelAdmin):
    list_display = ('nickname', 'game', 'score')
    list_filter = ('game',)
    search_fields = ('nickname', 'game__pin')
    raw_id_fields = ('game', 'user')
    
# Registrando outros modelos (Exemplos, mantenha os seus)
admin.site.register(PalavraChave)
admin.site.register(OrgaoPCI)
admin.site.register(BancaPCI)
admin.site.register(NivelEscolaridadePCI)
admin.site.register(CargoPCI)
admin.site.register(ProvaPCIConcurso)
admin.site.register(TipoNormaPlanalto)
admin.site.register(LeiPlanalto)
admin.site.register(ConcursoNoBrasil)
admin.site.register(NoticiaPCICapa)
admin.site.register(Organizacao)
admin.site.register(StatusConcurso)