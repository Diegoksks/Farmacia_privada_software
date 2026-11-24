from django import forms

from .validators import normalizar_rut


class BootstrapFormMixin:
    """Aplica las clases de Bootstrap a los widgets del formulario, para no
    repetir el estilo campo por campo en cada template."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo, forms.ModelChoiceField):
                if not campo.empty_label or str(campo.empty_label) in ('- Select an option -', '---------'):
                    campo.empty_label = '- Seleccione una opción -'
            elif isinstance(campo, (forms.ChoiceField, forms.TypedChoiceField)):
                nuevas_choices = []
                for item in getattr(campo, 'choices', []):
                    if isinstance(item, (list, tuple)) and len(item) == 2:
                        val, txt = item
                        if str(txt) in ('- Select an option -', '---------'):
                            nuevas_choices.append((val, '- Seleccione una opción -'))
                            continue
                    nuevas_choices.append(item)
                campo.choices = nuevas_choices
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                clase = 'form-check-input'
            elif isinstance(widget, forms.Select):
                clase = 'form-select'
            else:
                clase = 'form-control'
            widget.attrs.setdefault('class', clase)


class NormalizarRutFormMixin:
    """Deja el RUT en formato canónico ANTES de validar. Sin esto, escribir un
    RUT ya registrado con puntos pasa la verificación de unicidad (compara el
    texto crudo) y recién revienta al guardar, cuando el modelo lo normaliza."""

    def clean_rut(self):
        valor = self.cleaned_data.get('rut')
        return normalizar_rut(valor) if valor else valor
