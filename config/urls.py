from django.contrib import admin
from django.urls import path

from oficina import views

urlpatterns = [
    path("", views.painel, name="painel"),
    path("os/<int:pk>/imprimir/", views.imprimir_os, name="imprimir_os"),
    path("financeiro/", views.financeiro, name="financeiro"),
    path("admin/", admin.site.urls),
]
