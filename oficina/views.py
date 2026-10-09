from datetime import date
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import F
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

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


@staff_member_required
def financeiro(request):
    hoje = timezone.localdate()
    try:
        inicio = date.fromisoformat(request.GET.get("inicio", ""))
    except ValueError:
        inicio = hoje.replace(day=1)
    try:
        fim = date.fromisoformat(request.GET.get("fim", ""))
    except ValueError:
        fim = hoje

    ordens = (
        OrdemServico.objects.filter(
            status__in=["concluida", "entregue"],
            concluida_em__date__range=(inicio, fim),
        )
        .select_related("veiculo__cliente")
        .prefetch_related("servicos", "pecas__peca")
    )
    servicos = pecas = descontos = custo = Decimal(0)
    for o in ordens:
        servicos += o.total_servicos
        pecas += o.total_pecas
        descontos += o.desconto
        custo += sum((p.peca.preco_custo * p.quantidade for p in o.pecas.all()), Decimal(0))
    faturamento = servicos + pecas - descontos
    contexto = {
        "inicio": inicio, "fim": fim, "ordens": ordens,
        "servicos": servicos, "pecas": pecas, "descontos": descontos,
        "faturamento": faturamento, "custo": custo, "lucro": faturamento - custo,
        "ticket_medio": faturamento / len(ordens) if ordens else Decimal(0),
    }
    return render(request, "oficina/financeiro.html", contexto)
