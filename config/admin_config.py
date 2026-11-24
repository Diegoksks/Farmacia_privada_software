from django.contrib.admin.apps import AdminConfig


class FarmaciaAdminConfig(AdminConfig):
    default_site = 'apps.usuarios.admin_site.FarmaciaAdminSite'
