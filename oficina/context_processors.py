from django.contrib import admin
from django.urls import reverse

# (rótulo, nome da url, ícone) — os ícones estão em templates/admin/menu_icone.html
MENU = [
    ("Painel", "painel", "painel"),
    ("Nova OS", "admin:oficina_ordemservico_add", "mais"),
    ("Ordens de serviço", "admin:oficina_ordemservico_changelist", "os"),
    ("Checklist", "admin:oficina_checklist_changelist", "checklist"),
    ("Clientes", "admin:oficina_cliente_changelist", "clientes"),
    ("Veículos", "admin:oficina_veiculo_changelist", "veiculo"),
    ("Histórico", "painel_lista", "historico"),
    ("Peças", "admin:oficina_peca_changelist", "peca"),
    ("Promoções", "admin:oficina_promocao_changelist", "promocao"),
    ("Financeiro", "financeiro", "financeiro"),
]


def menu(request):
    """Monta o menu lateral para as telas do admin e as telas próprias."""
    user = getattr(request, "user", None)
    if not (user and user.is_staff):
        return {}
    itens, ativo = [], None
    for rotulo, nome, icone in MENU:
        url = reverse(nome, args=["historico"]) if nome == "painel_lista" else reverse(nome)
        itens.append({"rotulo": rotulo, "url": url, "icone": icone})
        # destaca o item cuja URL é o maior prefixo do caminho atual
        if request.path.startswith(url) and (ativo is None or len(url) > len(ativo["url"])):
            ativo = itens[-1]
    telas_proprias = {"/veiculo/": "historico", "/promocao/": "promocao", "/checklist/": "checklist"}  # histórico e divulgação
    for prefixo, icone in telas_proprias.items():
        if request.path.startswith(prefixo):
            ativo = next(i for i in itens if i["icone"] == icone)
    if ativo:
        ativo["ativo"] = True
    if user.is_superuser:
        itens.append({"rotulo": "Usuários", "url": reverse("admin:auth_user_changelist"), "icone": "usuarios",
                      "ativo": request.path.startswith(reverse("admin:auth_user_changelist"))})
    contexto = {"menu_lateral": itens, "is_nav_sidebar_enabled": True}
    # telas próprias: mesmo cabeçalho e links de usuário do admin
    if not request.path.startswith("/admin/"):
        contexto = {**admin.site.each_context(request), **contexto}
    return contexto
