from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import F
from django.shortcuts import get_object_or_404, render

from .models import OrdemServico, Peca


@staff_member_required
def painel(request):
    ordens = OrdemServico.objects.select_related("veiculo__cliente")
    contexto = {
        "abertas": ordens.exclude(status__in=["entregue", "cancelada"]),
        "estoque_baixo": Peca.objects.filter(estoque__lte=F("estoque_minimo")),
    }
    return render(request, "oficina/painel.html", contexto)


@staff_member_required
def imprimir_os(request, pk):
    ordem = get_object_or_404(OrdemServico.objects.select_related("veiculo__cliente"), pk=pk)
    return render(request, "oficina/imprimir_os.html", {"os": ordem})
