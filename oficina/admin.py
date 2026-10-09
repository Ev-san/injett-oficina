from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Cliente, OrdemServico, Peca, PecaOS, ServicoOS, Veiculo

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
    list_display = ["placa", "tipo", "marca", "modelo", "ano", "tensao", "cliente"]
    list_filter = ["tipo", "tensao"]
    search_fields = ["placa", "modelo", "cliente__nome"]
    autocomplete_fields = ["cliente"]


@admin.register(Peca)
class PecaAdmin(admin.ModelAdmin):
    list_display = ["descricao", "codigo", "preco_venda", "estoque", "alerta"]
    search_fields = ["descricao", "codigo"]

    @admin.display(description="Situação")
    def alerta(self, obj):
        return "⚠ Estoque baixo" if obj.estoque_baixo else "OK"


class ServicoInline(admin.TabularInline):
    model = ServicoOS
    extra = 1


class PecaInline(admin.TabularInline):
    model = PecaOS
    extra = 1
    autocomplete_fields = ["peca"]


@admin.register(OrdemServico)
class OrdemServicoAdmin(admin.ModelAdmin):
    list_display = ["id", "veiculo", "cliente", "status", "aberta_em", "valor_total", "imprimir", "whatsapp"]
    list_filter = ["status", "veiculo__tipo"]
    search_fields = ["veiculo__placa", "veiculo__cliente__nome"]
    autocomplete_fields = ["veiculo"]
    inlines = [ServicoInline, PecaInline]
    readonly_fields = ["valor_total"]

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
