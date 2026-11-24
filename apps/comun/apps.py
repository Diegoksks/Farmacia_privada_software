from django.apps import AppConfig
import django.db.models.fields as dj_fields


class ComunConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.comun'
    label = 'comun'
    verbose_name = 'Común'

    def ready(self):
        dj_fields.BLANK_CHOICE_LABEL = '- Seleccione una opción -'
