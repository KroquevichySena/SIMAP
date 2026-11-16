from django.contrib.admin.apps import AdminConfig


class SimapAdminConfig(AdminConfig):
    default_site = "SIMAP.admin_site.SimapAdminSite"
