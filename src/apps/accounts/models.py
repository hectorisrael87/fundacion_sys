from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    telefono = models.CharField(max_length=50, blank=True)
    cargo = models.CharField(max_length=200, blank=True)
    area = models.CharField(max_length=200, blank=True)

    ci = models.CharField(max_length=50, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        nombre = self.user.get_full_name() or self.user.username
        return f"{nombre} ({self.cargo})"
