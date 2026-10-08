from decimal import Decimal

from django.db import models


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
