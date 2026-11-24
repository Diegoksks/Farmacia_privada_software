from django.db import models
from django.conf import settings

class ChatMensaje(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_historial')
    mensaje_usuario = models.TextField()
    respuesta_bot = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha']
        verbose_name = 'Mensaje de Chat'
        verbose_name_plural = 'Historial de Chat'

    def __str__(self):
        return f"Chat de {self.usuario} - {self.fecha.strftime('%d/%m/%Y %H:%M')}"
