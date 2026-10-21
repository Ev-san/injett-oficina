from datetime import date, timedelta
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Exists, F, Max, OuterRef, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from .models import Checklist, Cliente, OrdemServico, Peca, Promocao, Veiculo

AVISO_DIAS = 15     # avisa revisões que vencem nos próximos dias
AVISO_KM = 1000     # ou quando faltar menos que esse KM


@staff_member_required
def painel(request):
    ordens = OrdemServico.objects.select_related("veiculo__cliente")
    hoje = timezone.localdate()
    concluidas_mes = ordens.filter(
        status__in=["concluida", "entregue"], concluida_em__date__gte=hoje.replace(day=1)
    ).prefetch_related("servicos", "pecas")
    fat_mes = sum((o.total for o in concluidas_mes), Decimal(0))
    fat_hoje = sum((o.total for o in concluidas_mes if timezone.localdate(o.concluida_em) == hoje), Decimal(0))
    abertas = ordens.exclude(status__in=["entregue", "cancelada"])
    contexto = {
        "hoje": hoje,
        "abertas": abertas,
        "estoque_baixo": Peca.objects.filter(estoque__lte=F("estoque_minimo")),
        "revisoes": revisoes_proximas(),
        "fat_hoje": fat_hoje,
        "fat_mes": fat_mes,
        "orcamentos": sum(1 for o in abertas if o.status == "orcamento"),
        "total_clientes": Cliente.objects.count(),
        "total_veiculos": Veiculo.objects.count(),
    }
    return render(request, "oficina/painel.html", contexto)


LISTAS_PAINEL = {"andamento": "Ordens em andamento", "revisoes": "Revisões a avisar", "estoque": "Peças com estoque baixo",
                 "historico": "Histórico dos veículos"}


@staff_member_required
def painel_lista(request, secao):
    """Cada lista que saiu da Visão Geral abre na sua própria tela."""
    if secao not in LISTAS_PAINEL:
        raise Http404
    contexto = {"secao": secao, "titulo": LISTAS_PAINEL[secao]}
    if secao == "andamento":
        contexto["abertas"] = OrdemServico.objects.select_related("veiculo__cliente").exclude(
            status__in=["entregue", "cancelada"])
    elif secao == "revisoes":
        contexto["revisoes"] = revisoes_proximas()
    elif secao == "historico":
        busca = request.GET.get("q", "").strip()
        veiculos = Veiculo.objects.select_related("cliente").annotate(n_os=Count("ordens"), ultima=Max("ordens__aberta_em"))
        if busca:
            veiculos = veiculos.filter(Q(placa__icontains=busca) | Q(modelo__icontains=busca) | Q(cliente__nome__icontains=busca))
        contexto.update(veiculos=veiculos, busca=busca)
    else:
        contexto["estoque_baixo"] = Peca.objects.filter(estoque__lte=F("estoque_minimo"))
    return render(request, "oficina/painel_lista.html", contexto)


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


def revisoes_proximas():
    """Última OS de cada veículo com revisão marcada que vence em breve ou já venceu."""
    hoje = timezone.localdate()
    os_posterior = OrdemServico.objects.filter(
        veiculo=OuterRef("veiculo"), aberta_em__gt=OuterRef("aberta_em"),
    ).exclude(status="cancelada")
    candidatas = (
        OrdemServico.objects.filter(status__in=["concluida", "entregue"])
        .filter(Q(proxima_revisao_km__isnull=False) | Q(proxima_revisao_data__isnull=False))
        .exclude(Exists(os_posterior))
        .select_related("veiculo__cliente")
    )
    revisoes = []
    for o in candidatas:
        km = o.veiculo.km or 0
        perto_data = o.proxima_revisao_data and o.proxima_revisao_data <= hoje + timedelta(days=AVISO_DIAS)
        perto_km = o.proxima_revisao_km and km >= o.proxima_revisao_km - AVISO_KM
        if perto_data or perto_km:
            o.vencida = o.revisao_vencida(hoje)
            revisoes.append(o)
    revisoes.sort(key=lambda o: (not o.vencida, o.proxima_revisao_data or date.max))
    return revisoes


@staff_member_required
def historico_veiculo(request, pk):
    veiculo = get_object_or_404(Veiculo.objects.select_related("cliente"), pk=pk)
    ordens = veiculo.ordens.exclude(status="cancelada").prefetch_related("servicos", "pecas__peca")
    contexto = {
        "veiculo": veiculo, "ordens": ordens,
        "total_gasto": sum((o.total for o in ordens if o.status in ("concluida", "entregue")), Decimal(0)),
    }
    return render(request, "oficina/historico_veiculo.html", contexto)


@staff_member_required
def divulgar_promocao(request, pk):
    promocao = get_object_or_404(Promocao, pk=pk)
    clientes = [(c, promocao.whatsapp_url(c)) for c in promocao.clientes()]
    return render(request, "oficina/divulgar_promocao.html", {"promocao": promocao, "clientes": clientes})


@staff_member_required
def imprimir_checklist(request, pk):
    checklist = get_object_or_404(Checklist.objects.select_related("ordem__veiculo__cliente"), pk=pk)
    link = request.build_absolute_uri(reverse("checklist_cliente", args=[checklist.token]))
    return render(request, "oficina/imprimir_checklist.html", {
        "c": checklist, "link": link, "whatsapp_url": checklist.whatsapp_url(link), "interno": True,
    })


def checklist_cliente(request, token):
    """Página pública (sem login) que o cliente abre pelo link do WhatsApp."""
    checklist = get_object_or_404(Checklist.objects.select_related("ordem__veiculo__cliente"), token=token)
    return render(request, "oficina/imprimir_checklist.html", {"c": checklist})
