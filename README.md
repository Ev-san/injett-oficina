# Injett Oficina

Sistema de gestão para oficinas mecânicas e auto elétricas (carros, caminhões e ônibus), desenvolvido em **Python + Django**.

Projeto criado a partir da minha experiência prática como eletricista automotivo de veículos leves e pesados, unida à formação em Análise e Desenvolvimento de Sistemas.

## Funcionalidades

- **Cadastro de clientes e veículos**: tipo de veículo (carro, caminhão, ônibus, moto), placa, tensão do sistema elétrico (12V/24V) e quilometragem
- **Ordens de serviço** com fluxo de status: orçamento → aprovada → em execução → concluída → entregue
- **Serviços e peças por OS**, com cálculo automático do total e do desconto
- **Controle de estoque**: a baixa é automática ao concluir a OS (sem baixa duplicada) e há um alerta de estoque mínimo
- **Impressão da OS** com campo para a assinatura do cliente
- **Envio do orçamento pelo WhatsApp** com um clique, com a mensagem formatada e os valores em R$
- **Relatório financeiro** por período: faturamento, custo das peças, lucro bruto e ticket médio
- **Painel inicial** com as OS em andamento e as peças com estoque baixo

## Tecnologias

- Python 3.13
- Django 6 (ORM, Admin customizado, templates)
- SQLite

## Como executar

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Acesse http://localhost:8000 e entre com o usuário criado.

## Testes

```bash
python manage.py test
```

Os testes automatizados cobrem o cálculo do total, a baixa de estoque sem duplicidade, o alerta de estoque mínimo, a mensagem do WhatsApp, o relatório financeiro e o controle de acesso.

## Estrutura

```
config/            configurações do projeto Django
oficina/
  models.py        Cliente, Veiculo, Peca, OrdemServico, ServicoOS, PecaOS
  admin.py         telas de cadastro, inlines e regras ao salvar a OS
  views.py         painel, impressão da OS e relatório financeiro
  tests.py         testes automatizados
  templates/       painel, OS para impressão e relatório financeiro
```

## Autor

**Evaristo Lourenço**: Análise e Desenvolvimento de Sistemas, com experiência em elétrica automotiva (leves e pesados).
