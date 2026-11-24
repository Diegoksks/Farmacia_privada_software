from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse


class FarmaciaAdminSite(admin.AdminSite):
    """AdminSite propio: /admin/login/ no debe existir como formulario aparte,
    porque no pasa por el 2FA del Administrador. Se redirige siempre al login
    de la app, que sí lo exige."""

    site_header = 'Farmacia Privada — Administración'
    site_title = 'Farmacia Privada'

    def login(self, request, extra_context=None):
        next_url = request.GET.get('next') or reverse('admin:index')
        return redirect(f"{reverse('usuarios:login')}?next={next_url}")
