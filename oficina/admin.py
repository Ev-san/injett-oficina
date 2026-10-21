from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Checklist, Cliente, OrdemServico, Peca, PecaOS, Promocao, ServicoOS, Veiculo

admin.site.site_header = "Injett Oficina"
admin.site.site_title = "Injett Oficina"
admin.site.index_title = "Gestão da oficina"
admin.site.site_url = "/"


class VeiculoInline(admin.TabularInline):
    model = Veiculo
    extra = 0


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ["nome", "telefone", "cpf_cnpj"]
    search_fields = ["nome", "telefone", "cpf_cnpj"]
    inlines = [VeiculoInline]


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = ["placa", "tipo", "marca", "modelo", "ano", "tensao", "km", "cliente", "historico"]
    list_filter = ["tipo", "tensao"]
    search_fields = ["placa", "modelo", "cliente__nome"]
    autocomplete_fields = ["cliente"]

    @admin.display(description="")
    def historico(self, obj):
        return format_html('<a href="{}">Histórico</a>', reverse("historico_veiculo", args=[obj.pk]))


@admin.register(Peca)
class PecaAdmin(admin.ModelAdmin):
    list_display = ["descricao", "codigo", "preco_venda", "estoque", "alerta"]
    search_fields = ["descricao", "codigo"]

    @admin.display(description="Situação")
    def alerta(self, obj):
        return "⚠ Estoque baixo" if obj.estoque_baixo else "OK"



@admin.register(Promocao)
class PromocaoAdmin(admin.ModelAdmin):
    list_display = ["titulo", "tipo_veiculo", "validade", "ativa", "divulgar"]
    list_filter = ["ativa", "tipo_veiculo"]
    list_editable = ["ativa"]

    @admin.display(description="")
    def divulgar(self, obj):
        return format_html('<a href="{}">Divulgar no WhatsApp</a>', reverse("divulgar_promocao", args=[obj.pk]))


class ServicoInline(admin.TabularInline):
    model = ServicoOS
    extra = 1


class PecaInline(admin.TabularInline):
    model = PecaOS
    extra = 1
    autocomplete_fields = ["peca"]


@admin.register(OrdemServico)
class OrdemServicoAdmin(admin.ModelAdmin):
    list_display = ["id", "veiculo", "cliente", "status", "aberta_em", "valor_total", "checklist", "imprimir", "whatsapp"]
    list_filter = ["status", "veiculo__tipo"]
    search_fields = ["veiculo__placa", "veiculo__cliente__nome"]
    autocomplete_fields = ["veiculo"]
    inlines = [ServicoInline, PecaInline]
    readonly_fields = ["valor_total", "historico_veiculo"]
    fieldsets = [
        (None, {"fields": ["veiculo", "historico_veiculo", "status", "km_entrada",
                           "defeito_relatado", "diagnostico", "desconto", "valor_total"]}),
        ("Lembrete de revisão", {
            "fields": ["proxima_revisao_km", "proxima_revisao_data", "revisao_obs"],
            "description": "Preencha para o veículo aparecer no painel quando a revisão estiver próxima.",
        }),
    ]

    @admin.display(description="Histórico")
    def historico_veiculo(self, obj):
        if not obj.pk:
            return "Salve a OS para ver o histórico do veículo."
        n = obj.veiculo.ordens.exclude(pk=obj.pk).exclude(status="cancelada").count()
        return format_html('<a href="{}" target="_blank">Ver histórico do veículo ({} OS anteriores)</a>',
                           reverse("historico_veiculo", args=[obj.veiculo_id]), n)

    @admin.display(description="")
    def checklist(self, obj):
        if hasattr(obj, "checklist"):
            return format_html('<a href="{}">Checklist ✔</a>', reverse("admin:oficina_checklist_change", args=[obj.checklist.pk]))
        return format_html('<a href="{}?ordem={}">Fazer checklist</a>', reverse("admin:oficina_checklist_add"), obj.pk)

    @admin.display(description="Total")
    def valor_total(self, obj):
        return f"R$ {obj.total:.2f}" if obj.pk else "-"

    @admin.display(description="")
    def imprimir(self, obj):
        return format_html('<a href="{}" target="_blank">Imprimir</a>', reverse("imprimir_os", args=[obj.pk]))

    @admin.display(description="")
    def whatsapp(self, obj):
        return format_html('<a href="{}" target="_blank">WhatsApp</a>', obj.whatsapp_url)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        ordem = form.instance
        if ordem.status in ("concluida", "entregue"):
            if not ordem.concluida_em:
                ordem.concluida_em = timezone.now()
                ordem.save(update_fields=["concluida_em"])
            ordem.baixar_estoque()



@admin.register(Checklist)
class ChecklistAdmin(admin.ModelAdmin):
    list_display = ["ordem", "veiculo", "feito_em", "defeitos", "imprimir"]  # imprimir = imprimir e compartilhar
    search_fields = ["ordem__veiculo__placa", "ordem__veiculo__cliente__nome"]
    autocomplete_fields = ["ordem"]
    fieldsets = [
        (None, {"fields": ["ordem", "km", "combustivel"]}),
        ("Itens vistoriados", {"fields": [campo for campo, _ in Checklist.ITENS]}),
        ("Observações", {"fields": ["avarias", "objetos", "observacoes"]}),
    ]
    radio_fields = {campo: admin.HORIZONTAL for campo, _ in Checklist.ITENS}

    @admin.display(description="Veículo")
    def veiculo(self, obj):
        return obj.ordem.veiculo

    @admin.display(description="Itens com defeito")
    def defeitos(self, obj):
        return ", ".join(obj.com_defeito) or "Nenhum"

    @admin.display(description="")
    def imprimir(self, obj):
        return format_html('<a href="{}" target="_blank">Imprimir / compartilhar</a>', reverse("imprimir_checklist", args=[obj.pk]))

    def response_add(self, request, obj, post_url_continue=None):
        # depois de salvar, volta para a OS
        if "_continue" not in request.POST and "_addanother" not in request.POST:
            return redirect("admin:oficina_ordemservico_change", obj.ordem_id)
        return super().response_add(request, obj, post_url_continue)
