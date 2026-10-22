"""Cria o usuário de demonstração e dados de exemplo (só se o banco estiver vazio)."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from oficina.models import Cliente, OrdemServico, Peca, PecaOS, Promocao, ServicoOS, Veiculo


class Command(BaseCommand):
    help = "Cria o usuário demo/demo12345 e dados de exemplo."

    def handle(self, *args, **options):
        if not User.objects.filter(username="demo").exists():
            User.objects.create_superuser("demo", "", "demo12345")
            self.stdout.write("Usuário demo criado.")

        if Cliente.objects.exists():
            self.stdout.write("Banco já tem dados; nada a popular.")
            return

        hoje = timezone.localdate()

        pecas = {
            p[0]: Peca.objects.create(codigo=p[0], descricao=p[1], preco_custo=Decimal(p[2]),
                                      preco_venda=Decimal(p[3]), estoque=p[4], estoque_minimo=p[5])
            for p in [
                ("ALT-24", "Alternador 24V 80A", "980.00", "1450.00", 3, 2),
                ("MP-12", "Motor de partida 12V", "620.00", "950.00", 1, 2),
                ("BAT-150", "Bateria 150Ah", "780.00", "1100.00", 6, 2),
                ("REL-40", "Relé auxiliar 40A", "12.00", "28.00", 40, 10),
                ("LAMP-H7", "Lâmpada H7 24V", "9.00", "22.00", 4, 10),
                ("FUS-KIT", "Kit de fusíveis lâmina", "15.00", "35.00", 12, 5),
            ]
        }

        joao = Cliente.objects.create(nome="João Ferreira", telefone="(11) 98888-1234",
                                      cpf_cnpj="123.456.789-00")
        transp = Cliente.objects.create(nome="Transportes Rota Sul Ltda", telefone="(11) 97777-4321",
                                        cpf_cnpj="12.345.678/0001-90")
        viacao = Cliente.objects.create(nome="Viação Bela Vista", telefone="(11) 96666-5555")
        maria = Cliente.objects.create(nome="Maria Souza", telefone="(11) 95555-8888")

        gol = Veiculo.objects.create(cliente=joao, tipo="carro", placa="FGH1A23", marca="Volkswagen",
                                     modelo="Gol 1.6", ano=2018, tensao="12V", km=84000)
        actros = Veiculo.objects.create(cliente=transp, tipo="caminhao", placa="RST2B45", marca="Mercedes-Benz",
                                        modelo="Actros 2651", ano=2021, tensao="24V", km=312000)
        fh = Veiculo.objects.create(cliente=transp, tipo="caminhao", placa="QWE3C67", marca="Volvo",
                                    modelo="FH 540", ano=2020, tensao="24V", km=401500)
        onibus = Veiculo.objects.create(cliente=viacao, tipo="onibus", placa="BUS4D89", marca="Marcopolo",
                                        modelo="Torino O500", ano=2019, tensao="24V", km=550000)
        Veiculo.objects.create(cliente=maria, tipo="moto", placa="MOT5E12", marca="Honda",
                               modelo="CG 160", ano=2022, tensao="12V", km=21000)

        def os_(veiculo, status, defeito, km, servicos, itens, dias=0, **extra):
            ordem = OrdemServico.objects.create(veiculo=veiculo, status=status, defeito_relatado=defeito,
                                                km_entrada=km, **extra)
            for desc, valor in servicos:
                ServicoOS.objects.create(ordem=ordem, descricao=desc, valor=Decimal(valor))
            for cod, qtd in itens:
                PecaOS.objects.create(ordem=ordem, peca=pecas[cod], quantidade=qtd)
            if status in ("concluida", "entregue"):
                ordem.baixar_estoque()
                OrdemServico.objects.filter(pk=ordem.pk).update(
                    concluida_em=timezone.now() - timedelta(days=dias),
                    aberta_em=timezone.now() - timedelta(days=dias + 1))
            return ordem

        os_(actros, "entregue", "Bateria não segura carga", 305000,
            [("Teste do sistema de carga", "180.00"), ("Troca do alternador", "250.00")], [("ALT-24", 1)],
            dias=40, proxima_revisao_km=315000, revisao_obs="Sistema de carga e baterias")
        os_(onibus, "entregue", "Luzes do salão piscando", 548000,
            [("Revisão do chicote do salão", "420.00")], [("REL-40", 3), ("FUS-KIT", 1)],
            dias=20, proxima_revisao_data=hoje + timedelta(days=5), revisao_obs="Iluminação interna")
        os_(gol, "concluida", "Não dá partida pela manhã", 84000,
            [("Diagnóstico elétrico", "120.00"), ("Troca do motor de partida", "150.00")], [("MP-12", 1)],
            dias=2)
        os_(fh, "execucao", "Painel apagando em movimento", 401500,
            [("Diagnóstico com scanner", "200.00")], [("REL-40", 2)])
        os_(fh, "aprovada", "Farol baixo queimando com frequência", 401500,
            [("Verificação de tensão nos faróis", "150.00")], [("LAMP-H7", 2)])
        os_(gol, "orcamento", "Ar-condicionado não liga", 84000,
            [("Diagnóstico do circuito do A/C", "120.00")], [])

        Promocao.objects.create(titulo="Revisão elétrica com 20% off", tipo_veiculo="caminhao",
                                descricao="Teste de baterias, alternador e partida.",
                                validade=hoje + timedelta(days=30))

        self.stdout.write(self.style.SUCCESS("Dados de exemplo criados."))
