from decimal import Decimal
from urllib.parse import unquote

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Cliente, OrdemServico, Peca, PecaOS, ServicoOS, Veiculo, brl


class BaseOficinaTest(TestCase):
    def setUp(self):
        cliente = Cliente.objects.create(nome="Transportes Teste", telefone="(11) 99999-0000")
        veiculo = Veiculo.objects.create(
            cliente=cliente, tipo="caminhao", placa="ABC1D23",
            marca="Volvo", modelo="FH 540", tensao="24V",
        )
        self.peca = Peca.objects.create(
            descricao="Relé 24V", preco_custo=Decimal("20"), preco_venda=Decimal("35"),
            estoque=5, estoque_minimo=2,
        )
        self.os = OrdemServico.objects.create(veiculo=veiculo, defeito_relatado="Farol não acende")
        ServicoOS.objects.create(ordem=self.os, descricao="Revisão chicote farol", valor=Decimal("150"))
        PecaOS.objects.create(ordem=self.os, peca=self.peca, quantidade=2)


class OrdemServicoTest(BaseOficinaTest):
    def test_preco_da_peca_vem_do_cadastro(self):
        self.assertEqual(self.os.pecas.get().preco_unitario, Decimal("35"))

    def test_total_com_desconto(self):
        self.os.desconto = Decimal("20")
        self.assertEqual(self.os.total_servicos, Decimal("150"))
        self.assertEqual(self.os.total_pecas, Decimal("70"))
        self.assertEqual(self.os.total, Decimal("200"))

    def test_baixa_de_estoque_acontece_uma_vez(self):
        self.os.baixar_estoque()
        self.os.baixar_estoque()
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.estoque, 3)
        self.assertFalse(self.peca.estoque_baixo)

    def test_alerta_de_estoque_minimo(self):
        self.peca.estoque = 2
        self.assertTrue(self.peca.estoque_baixo)

    def test_formato_real_brasileiro(self):
        self.assertEqual(brl(Decimal("1234.5")), "1.234,50")

    def test_link_whatsapp(self):
        url = self.os.whatsapp_url
        self.assertTrue(url.startswith("https://wa.me/5511999990000?text="))
        texto = unquote(url.split("text=")[1])
        self.assertIn("*TOTAL: R$ 220,00*", texto)
        self.assertIn("Podemos aprovar o serviço?", texto)


class ViewsTest(BaseOficinaTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser("admin", "", "senha"))

    def test_paginas_exigem_login(self):
        self.client.logout()
        resposta = self.client.get(reverse("painel"))
        self.assertEqual(resposta.status_code, 302)

    def test_painel_e_impressao(self):
        self.assertContains(self.client.get(reverse("painel")), "ABC1D23")
        self.assertContains(self.client.get(reverse("imprimir_os", args=[self.os.pk])), "Farol não acende")

    def test_financeiro_conta_so_os_concluidas(self):
        resposta = self.client.get(reverse("financeiro"))
        self.assertEqual(resposta.context["faturamento"], 0)

        self.os.status = "entregue"
        self.os.concluida_em = timezone.now()
        self.os.save()
        resposta = self.client.get(reverse("financeiro"))
        self.assertEqual(resposta.context["faturamento"], Decimal("220"))
        self.assertEqual(resposta.context["custo"], Decimal("40"))
        self.assertEqual(resposta.context["lucro"], Decimal("180"))
