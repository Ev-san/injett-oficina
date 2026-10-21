from django.contrib import admin
from django.urls import path

from oficina import views

urlpatterns = [
    path("", views.painel, name="painel"),
    path("painel/<str:secao>/", views.painel_lista, name="painel_lista"),
    path("os/<int:pk>/imprimir/", views.imprimir_os, name="imprimir_os"),
    path("veiculo/<int:pk>/historico/", views.historico_veiculo, name="historico_veiculo"),
    path("promocao/<int:pk>/divulgar/", views.divulgar_promocao, name="divulgar_promocao"),
    path("checklist/<int:pk>/imprimir/", views.imprimir_checklist, name="imprimir_checklist"),
    path("c/<uuid:token>/", views.checklist_cliente, name="checklist_cliente"),
    path("financeiro/", views.financeiro, name="financeiro"),
    path("admin/", admin.site.urls),
]
