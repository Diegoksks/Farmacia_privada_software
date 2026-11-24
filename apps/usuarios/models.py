import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.comun.validators import normalizar_rut, validar_rut


class Usuario(AbstractUser):
    """Usuario del sistema. El rol determina tanto reglas de negocio (2FA,
    acceso a /admin) como el Group de Django al que se sincroniza para
    permisos finos por modelo."""

    class Rol(models.TextChoices):
        ADMINISTRADOR = 'ADMINISTRADOR', 'Administrador'
        VENDEDOR = 'VENDEDOR', 'Vendedor'
        TECNICO_FARMACIA = 'TECNICO_FARMACIA', 'Técnico en Farmacia'
        QUIMICO_FARMACEUTICO = 'QUIMICO_FARMACEUTICO', 'Químico Farmacéutico'

    email = models.EmailField(blank=False)
    rut = models.CharField(max_length=12, unique=True, validators=[validar_rut])
    telefono = models.CharField(max_length=20, blank=True)
    rol = models.CharField(max_length=25, choices=Rol.choices)

    REQUIRED_FIELDS = ['email', 'rut', 'rol']

    def clean(self):
        super().clean()
        if self.rol == self.Rol.ADMINISTRADOR and not self.email:
            raise ValidationError({'email': 'El rol Administrador requiere un correo para el 2FA.'})

    def save(self, *args, **kwargs):
        if self.rut:
            self.rut = normalizar_rut(self.rut)
        # Los 4 roles son personal interno de la farmacia (no hay portal para
        # Cliente/Paciente) y varias operaciones solo tienen interfaz vía
        # /admin todavía, así que is_staff va para cualquier rol; lo que cada
        # uno puede ver o hacer ahí lo sigue acotando su Group de permisos.
        if self.rol:
            self.is_staff = True
        super().save(*args, **kwargs)
        grupo, _ = Group.objects.get_or_create(name=self.get_rol_display())
        self.groups.set([grupo])


class CodigoVerificacion(models.Model):
    """Código de un solo uso para el segundo factor de autenticación (rol Administrador)."""

    VIGENCIA_MINUTOS = 5

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='codigos_2fa')
    codigo = models.CharField(max_length=6)
    creado = models.DateTimeField(auto_now_add=True)
    usado = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Código de verificación'
        verbose_name_plural = 'Códigos de verificación'

    @classmethod
    def generar_para(cls, usuario):
        codigo = f'{secrets.randbelow(1_000_000):06d}'
        return cls.objects.create(usuario=usuario, codigo=codigo)

    def vigente(self):
        return not self.usado and timezone.now() <= self.creado + timedelta(minutes=self.VIGENCIA_MINUTOS)
