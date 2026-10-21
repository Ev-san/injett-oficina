import re
import uuid
from urllib.parse import quote
from decimal import Decimal

from django.db import models


def brl(valor):
    return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def whatsapp_link(telefone, texto):
    numero = re.sub(r"\D", "", telefone or "")
    if numero and len(numero) <= 11:
        numero = "55" + numero
    return f"https://wa.me/{numero}?text={quote(texto)}"


class Cliente(models.Model):
    nome = models.CharField(max_length=150)
    cpf_cnpj = models.CharField("CPF/CNPJ", max_length=18, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    endereco = models.CharField("Endereço", max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Veiculo(models.Model):
    TIPOS = [
        ("carro", "Carro"),
        ("caminhao", "Caminhão"),
        ("onibus", "Ônibus"),
        ("moto", "Moto"),
        ("outro", "Outro"),
    ]
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="veiculos")
    tipo = models.CharField(max_length=10, choices=TIPOS, default="carro")
    placa = models.CharField(max_length=8, unique=True)
    marca = models.CharField(max_length=50)
    modelo = models.CharField(max_length=80)
    ano = models.PositiveIntegerField(null=True, blank=True)
    tensao = models.CharField("Tensão", max_length=5, choices=[("12V", "12V"), ("24V", "24V")], default="12V")
    km = models.PositiveIntegerField("KM", null=True, blank=True)

    class Meta:
        verbose_name = "Veículo"
        ordering = ["placa"]

    def __str__(self):
        return f"{self.placa} - {self.marca} {self.modelo}"


class Promocao(models.Model):
    titulo = models.CharField("Título", max_length=100, help_text="Ex.: Revisão elétrica com 20% off")
    descricao = models.TextField("Descrição", blank=True)
    tipo_veiculo = models.CharField("Para veículos", max_length=10, choices=Veiculo.TIPOS, blank=True,
                                    help_text="Deixe em branco para todos os clientes")
    validade = models.DateField("Válida até", null=True, blank=True)
    ativa = models.BooleanField(default=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Promoção"
        verbose_name_plural = "Promoções"
        ordering = ["-criada_em"]

    def __str__(self):
        return self.titulo

    def clientes(self):
        """Clientes com telefone que podem receber a promoção."""
        qs = Cliente.objects.exclude(telefone="")
        if self.tipo_veiculo:
            qs = qs.filter(veiculos__tipo=self.tipo_veiculo).distinct()
        return qs

    def mensagem(self, cliente):
        linhas = [f"Olá, {cliente.nome}! A *Injett Oficina* tem uma promoção para você:", "", f"*{self.titulo}*"]
        if self.descricao:
            linhas.append(self.descricao)
        if self.validade:
            linhas += ["", f"Válida até {self.validade:%d/%m/%Y}."]
        linhas.append("Quer agendar?")
        return "\n".join(linhas)

    def whatsapp_url(self, cliente):
        return whatsapp_link(cliente.telefone, self.mensagem(cliente))


class Peca(models.Model):
    codigo = models.CharField("Código", max_length=40, blank=True)
    descricao = models.CharField("Descrição", max_length=150)
    preco_custo = models.DecimalField("Preço de custo", max_digits=10, decimal_places=2, default=0)
    preco_venda = models.DecimalField("Preço de venda", max_digits=10, decimal_places=2, default=0)
    estoque = models.IntegerField(default=0)
    estoque_minimo = models.IntegerField("Estoque mínimo", default=0)

    class Meta:
        verbose_name = "Peça"
        ordering = ["descricao"]

    def __str__(self):
        return self.descricao

    @property
    def estoque_baixo(self):
        return self.estoque <= self.estoque_minimo


class OrdemServico(models.Model):
    STATUS = [
        ("orcamento", "Orçamento"),
        ("aprovada", "Aprovada"),
        ("execucao", "Em execução"),
        ("concluida", "Concluída"),
        ("entregue", "Entregue"),
        ("cancelada", "Cancelada"),
    ]
    veiculo = models.ForeignKey(Veiculo, on_delete=models.PROTECT, related_name="ordens")
    status = models.CharField(max_length=10, choices=STATUS, default="orcamento")
    defeito_relatado = models.TextField("Defeito relatado")
    diagnostico = models.TextField("Diagnóstico", blank=True)
    km_entrada = models.PositiveIntegerField("KM entrada", null=True, blank=True)
    desconto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    aberta_em = models.DateTimeField(auto_now_add=True)
    concluida_em = models.DateTimeField(null=True, blank=True)
    estoque_baixado = models.BooleanField(default=False, editable=False)
    proxima_revisao_km = models.PositiveIntegerField("Próxima revisão (KM)", null=True, blank=True)
    proxima_revisao_data = models.DateField("Próxima revisão (data)", null=True, blank=True)
    revisao_obs = models.CharField("O que revisar", max_length=200, blank=True,
                                   help_text="Ex.: troca de óleo, revisão do alternador")

    class Meta:
        verbose_name = "Ordem de serviço"
        verbose_name_plural = "Ordens de serviço"
        ordering = ["-aberta_em"]

    def __str__(self):
        return f"OS #{self.pk} - {self.veiculo.placa}"

    @property
    def cliente(self):
        return self.veiculo.cliente

    @property
    def total_servicos(self):
        return sum((s.valor for s in self.servicos.all()), Decimal(0))

    @property
    def total_pecas(self):
        return sum((p.subtotal for p in self.pecas.all()), Decimal(0))

    @property
    def total(self):
        return self.total_servicos + self.total_pecas - self.desconto

    def mensagem_whatsapp(self):
        linhas = [
            f"*Injett Oficina* - {self.get_status_display()} OS #{self.pk}",
            f"Cliente: {self.cliente.nome}",
            f"Veículo: {self.veiculo}",
            "",
        ]
        if self.diagnostico:
            linhas += [f"Diagnóstico: {self.diagnostico}", ""]
        servicos, pecas = self.servicos.all(), self.pecas.all()
        if servicos:
            linhas.append("*Serviços:*")
            linhas += [f"- {s.descricao}: R$ {brl(s.valor)}" for s in servicos]
        if pecas:
            linhas.append("*Peças:*")
            linhas += [f"- {p.quantidade}x {p.peca.descricao}: R$ {brl(p.subtotal)}" for p in pecas]
        if self.desconto:
            linhas.append(f"Desconto: R$ {brl(self.desconto)}")
        linhas.append(f"*TOTAL: R$ {brl(self.total)}*")
        if self.status == "orcamento":
            linhas += ["", "Podemos aprovar o serviço?"]
        return "\n".join(linhas)

    @property
    def whatsapp_url(self):
        return whatsapp_link(self.cliente.telefone, self.mensagem_whatsapp())

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # mantém o KM do veículo atualizado com o maior KM registrado
        if self.km_entrada and self.km_entrada > (self.veiculo.km or 0):
            Veiculo.objects.filter(pk=self.veiculo_id).update(km=self.km_entrada)
            self.veiculo.km = self.km_entrada

    @property
    def tem_revisao(self):
        return bool(self.proxima_revisao_km or self.proxima_revisao_data)

    def revisao_vencida(self, hoje):
        km = self.veiculo.km or 0
        return bool(
            (self.proxima_revisao_data and self.proxima_revisao_data <= hoje)
            or (self.proxima_revisao_km and km >= self.proxima_revisao_km)
        )

    def mensagem_revisao(self):
        prazo = []
        if self.proxima_revisao_data:
            prazo.append(f"em {self.proxima_revisao_data:%d/%m/%Y}")
        if self.proxima_revisao_km:
            prazo.append(f"aos {self.proxima_revisao_km:,} km".replace(",", "."))
        linhas = [
            f"Olá, {self.cliente.nome}! Aqui é da *Injett Oficina*.",
            f"A revisão do seu veículo {self.veiculo} está prevista {' ou '.join(prazo)}.",
        ]
        if self.revisao_obs:
            linhas.append(f"Itens: {self.revisao_obs}.")
        linhas.append("Vamos agendar?")
        return "\n".join(linhas)

    @property
    def whatsapp_revisao_url(self):
        return whatsapp_link(self.cliente.telefone, self.mensagem_revisao())

    def baixar_estoque(self):
        """Desconta do estoque as peças usadas (uma única vez)."""
        if self.estoque_baixado:
            return
        for item in self.pecas.select_related("peca"):
            item.peca.estoque -= item.quantidade
            item.peca.save(update_fields=["estoque"])
        self.estoque_baixado = True
        self.save(update_fields=["estoque_baixado"])


class ServicoOS(models.Model):
    ordem = models.ForeignKey(OrdemServico, on_delete=models.CASCADE, related_name="servicos")
    descricao = models.CharField("Descrição", max_length=200)
    valor = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Serviço"


class PecaOS(models.Model):
    ordem = models.ForeignKey(OrdemServico, on_delete=models.CASCADE, related_name="pecas")
    peca = models.ForeignKey(Peca, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField("Preço unitário", max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Peça utilizada"
        verbose_name_plural = "Peças utilizadas"

    def save(self, *args, **kwargs):
        if self.preco_unitario is None:
            self.preco_unitario = self.peca.preco_venda
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return (self.preco_unitario or 0) * self.quantidade


class Checklist(models.Model):
    """Vistoria do veículo na entrada da oficina, assinada pelo cliente."""
    SITUACAO = [("ok", "OK"), ("defeito", "Com defeito"), ("nao_possui", "Não possui")]
    COMBUSTIVEL = [("reserva", "Reserva"), ("1/4", "1/4"), ("1/2", "1/2"), ("3/4", "3/4"), ("cheio", "Cheio")]
    # (campo, rótulo) dos itens vistoriados
    ITENS = [
        ("farois", "Faróis"), ("lanternas", "Lanternas e luz de freio"), ("setas", "Setas / pisca-alerta"),
        ("buzina", "Buzina"), ("painel", "Painel e luzes de alerta"), ("bateria", "Bateria"),
        ("limpador", "Limpador de para-brisa"), ("vidros", "Vidros e retrovisores"),
        ("pneus", "Pneus"), ("estepe", "Estepe"), ("macaco", "Macaco e chave de roda"),
        ("triangulo", "Triângulo"), ("extintor", "Extintor"), ("tacografo", "Tacógrafo"),
        ("som", "Rádio / som"), ("documentos", "Documentos do veículo"),
    ]

    ordem = models.OneToOneField(OrdemServico, on_delete=models.CASCADE, related_name="checklist",
                                 verbose_name="Ordem de serviço")
    km = models.PositiveIntegerField("KM", null=True, blank=True)
    combustivel = models.CharField("Combustível", max_length=8, choices=COMBUSTIVEL, blank=True)
    for _campo, _rotulo in ITENS:
        locals()[_campo] = models.CharField(_rotulo, max_length=10, choices=SITUACAO, default="ok")
    del _campo, _rotulo
    avarias = models.TextField("Avarias na lataria / pintura", blank=True)
    objetos = models.TextField("Objetos deixados no veículo", blank=True)
    observacoes = models.TextField("Observações", blank=True)
    feito_em = models.DateTimeField(auto_now_add=True)
    # chave do link público enviado ao cliente (não dá para adivinhar como um número sequencial)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        verbose_name = "Checklist de entrada"
        verbose_name_plural = "Checklists de entrada"
        ordering = ["-feito_em"]

    def __str__(self):
        return f"Checklist da {self.ordem}"

    def itens(self):
        """Lista (rótulo, situação, código) para exibir/imprimir."""
        return [(rotulo, getattr(self, f"get_{campo}_display")(), getattr(self, campo))
                for campo, rotulo in self.ITENS]

    @property
    def com_defeito(self):
        return [rotulo for rotulo, _, codigo in self.itens() if codigo == "defeito"]

    def mensagem_whatsapp(self, link):
        linhas = [
            f"Olá, {self.ordem.cliente.nome}! Aqui é da *Injett Oficina*.",
            f"Segue o checklist de entrada do seu veículo {self.ordem.veiculo} (OS #{self.ordem_id}):",
            "",
            f"KM: {self.km or '-'} | Combustível: {self.get_combustivel_display() or '-'}",
        ]
        if self.com_defeito:
            linhas.append(f"*Itens com defeito:* {', '.join(self.com_defeito)}")
        else:
            linhas.append("Todos os itens vistoriados estão OK.")
        if self.avarias:
            linhas.append(f"Avarias: {self.avarias}")
        if self.objetos:
            linhas.append(f"Objetos no veículo: {self.objetos}")
        linhas += ["", f"Checklist completo: {link}"]
        return "\n".join(linhas)

    def whatsapp_url(self, link):
        return whatsapp_link(self.ordem.cliente.telefone, self.mensagem_whatsapp(link))

    def save(self, *args, **kwargs):
        if self.km is None:
            self.km = self.ordem.km_entrada
        super().save(*args, **kwargs)
