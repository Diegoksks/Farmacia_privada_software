import re

from django.core.exceptions import ValidationError


def validar_rut(rut):
    """Valida formato y dígito verificador de un RUT chileno (con o sin puntos/guion)."""
    limpio = rut.upper().replace('.', '').replace('-', '')
    if not re.fullmatch(r'\d{7,8}[0-9K]', limpio):
        raise ValidationError('Formato de RUT inválido. Use el formato 12345678-9.')

    cuerpo, dv = limpio[:-1], limpio[-1]
    suma = 0
    multiplicador = 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplicador
        multiplicador = multiplicador + 1 if multiplicador < 7 else 2

    resto = 11 - (suma % 11)
    dv_esperado = {11: '0', 10: 'K'}.get(resto, str(resto))

    if dv != dv_esperado:
        raise ValidationError('El RUT ingresado no es válido (dígito verificador incorrecto).')


def normalizar_rut(rut):
    """Devuelve el RUT en formato canónico 12345678-9, sin puntos y con guion."""
    limpio = rut.upper().replace('.', '').replace('-', '')
    return f'{limpio[:-1]}-{limpio[-1]}'
