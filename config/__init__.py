import django.db.models.fields as _fields

# Override default blank choice label for Django 6+ to Spanish across all forms and models
_fields.BLANK_CHOICE_LABEL = '- Seleccione una opción -'
