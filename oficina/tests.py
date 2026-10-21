from decimal import Decimal
from urllib.parse import unquote

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Checklist, Cliente, OrdemServico, Peca, PecaOS, Promocao, ServicoOS, Veiculo, brl


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
        self.assertContains(self.client.get(reverse("painel_lista", args=["andamento"])), "ABC1D23")
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


class HistoricoRevisaoTest(BaseOficinaTest):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_superuser("admin", "a@a.com", "senha")
        self.client.force_login(self.user)

    def test_km_da_os_atualiza_veiculo(self):
        self.os.km_entrada = 150000
        self.os.save()
        self.assertEqual(Veiculo.objects.get().km, 150000)
        self.os.km_entrada = 100  # KM menor não regride o veículo
        self.os.save()
        self.assertEqual(Veiculo.objects.get().km, 150000)

    def test_historico_lista_os_do_veiculo(self):
        resp = self.client.get(reverse("historico_veiculo", args=[self.os.veiculo_id]))
        self.assertContains(resp, f"OS #{self.os.pk}")
        self.assertContains(resp, "Revisão chicote farol")

    def test_revisao_vencida_aparece_no_painel(self):
        self.os.status = "concluida"
        self.os.km_entrada = 150000
        self.os.proxima_revisao_km = 150500
        self.os.revisao_obs = "troca de óleo"
        self.os.save()
        resp = self.client.get(reverse("painel_lista", args=["revisoes"]))
        self.assertEqual(resp.context["revisoes"], [self.os])
        self.assertContains(resp, "Avisar no WhatsApp")

    def test_revisao_some_quando_veiculo_volta(self):
        self.os.status = "concluida"
        self.os.proxima_revisao_data = timezone.localdate()
        self.os.save()
        OrdemServico.objects.create(veiculo=self.os.veiculo, defeito_relatado="Revisão")
        self.assertEqual(self.client.get(reverse("painel")).context["revisoes"], [])

    def test_revisao_distante_nao_aparece(self):
        self.os.status = "concluida"
        self.os.proxima_revisao_data = timezone.localdate() + timezone.timedelta(days=90)
        self.os.save()
        self.assertEqual(self.client.get(reverse("painel")).context["revisoes"], [])

    def test_mensagem_revisao(self):
        self.os.proxima_revisao_km = 160000
        self.os.revisao_obs = "troca de óleo"
        self.assertIn("aos 160.000 km", self.os.mensagem_revisao())
        self.assertIn("55119999", unquote(self.os.whatsapp_revisao_url))


class MenuLateralTest(BaseOficinaTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser("admin", "a@a.com", "senha"))

    def test_menu_aparece_e_marca_item_ativo(self):
        for nome, rotulo in [("financeiro", "Financeiro"), ("admin:oficina_veiculo_changelist", "Veículos")]:
            resp = self.client.get(reverse(nome))
            self.assertContains(resp, 'id="menu-lateral"')
            ativos = [i["rotulo"] for i in resp.context["menu_lateral"] if i.get("ativo")]
            self.assertEqual(ativos, [rotulo])

    def test_menu_nao_aparece_no_login(self):
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("admin:login")), 'id="menu-lateral"')


class PromocaoTest(BaseOficinaTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser("admin", "a@a.com", "senha"))
        Cliente.objects.create(nome="Sem telefone")
        carro = Cliente.objects.create(nome="Dono de carro", telefone="11 98888-0000")
        Veiculo.objects.create(cliente=carro, placa="CAR1234", marca="Fiat", modelo="Uno")

    def test_publico_por_tipo_de_veiculo(self):
        promo = Promocao.objects.create(titulo="Revisão de caminhão", tipo_veiculo="caminhao")
        self.assertEqual([c.nome for c in promo.clientes()], ["Transportes Teste"])
        todos = Promocao.objects.create(titulo="Bateria em oferta")
        self.assertEqual(todos.clientes().count(), 2)

    def test_pagina_de_divulgacao(self):
        promo = Promocao.objects.create(titulo="Bateria em oferta", descricao="20% off")
        resp = self.client.get(reverse("divulgar_promocao", args=[promo.pk]))
        self.assertContains(resp, "Enviar no WhatsApp", count=2)
        self.assertIn("Bateria em oferta", unquote(promo.whatsapp_url(Cliente.objects.get(nome="Dono de carro"))))
        ativos = [i["rotulo"] for i in resp.context["menu_lateral"] if i.get("ativo")]
        self.assertEqual(ativos, ["Promoções"])


class ChecklistTest(BaseOficinaTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser("admin", "a@a.com", "senha"))

    def test_checklist_herda_km_e_lista_defeitos(self):
        self.os.km_entrada = 98000
        self.os.save()
        c = Checklist.objects.create(ordem=self.os, farois="defeito", estepe="nao_possui")
        self.assertEqual(c.km, 98000)
        self.assertEqual(c.com_defeito, ["Faróis"])

    def test_impressao_e_menu(self):
        c = Checklist.objects.create(ordem=self.os, combustivel="1/2", avarias="Risco na porta")
        resp = self.client.get(reverse("imprimir_checklist", args=[c.pk]))
        self.assertContains(resp, "Risco na porta")
        resp = self.client.get(reverse("admin:oficina_checklist_changelist"))
        ativos = [i["rotulo"] for i in resp.context["menu_lateral"] if i.get("ativo")]
        self.assertEqual(ativos, ["Checklist"])

    def test_formulario_abre_com_os_preenchida(self):
        resp = self.client.get(reverse("admin:oficina_checklist_add") + f"?ordem={self.os.pk}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["adminform"].form.initial["ordem"], str(self.os.pk))


class CompartilharChecklistTest(BaseOficinaTest):
    def setUp(self):
        super().setUp()
        self.checklist = Checklist.objects.create(ordem=self.os, farois="defeito", objetos="Notebook")

    def test_link_publico_abre_sem_login(self):
        resp = self.client.get(reverse("checklist_cliente", args=[self.checklist.token]))
        self.assertContains(resp, "Checklist de entrada")
        self.assertNotContains(resp, "Enviar ao cliente")  # sem botões internos

    def test_link_com_token_errado_da_404(self):
        resp = self.client.get(reverse("checklist_cliente", args=["00000000-0000-0000-0000-000000000000"]))
        self.assertEqual(resp.status_code, 404)

    def test_tela_interna_tem_whatsapp_com_link(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@a.com", "senha"))
        resp = self.client.get(reverse("imprimir_checklist", args=[self.checklist.pk]))
        self.assertContains(resp, "Enviar ao cliente pelo WhatsApp")
        msg = unquote(resp.context["whatsapp_url"])
        self.assertIn("Itens com defeito:* Faróis", msg)
        self.assertIn(f"/c/{self.checklist.token}/", msg)
