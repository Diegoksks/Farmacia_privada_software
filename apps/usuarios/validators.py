# Re-exportado desde apps.comun: la migración 0001_initial ya aplicada
# referencia apps.usuarios.validators.validar_rut, así que este módulo debe
# seguir existiendo con ese nombre disponible aunque la lógica viva en comun.
from apps.comun.validators import validar_rut  # noqa: F401
