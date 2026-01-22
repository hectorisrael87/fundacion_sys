from django.db import models

from django.db import models

class Provider(models.Model):
    codigo = models.CharField(max_length=20, unique=True, null=True, blank=True)
  # opcional

    nombre_empresa = models.CharField(max_length=200)
    direccion = models.CharField(max_length=250, blank=True)
    telefono = models.CharField(max_length=50, blank=True)

    datos_transferencia = models.CharField(max_length=250, blank=True)
    entidad = models.CharField(max_length=100, blank=True)  # Banco / Entidad
    nro_cuenta = models.CharField(max_length=50, blank=True)

    ci = models.CharField(max_length=30, blank=True)
    nit = models.CharField(max_length=30, blank=True)
    descripcion = models.TextField(blank=True)

    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre_empresa



class Product(models.Model):
    nombre = models.CharField(max_length=200)
    unidad = models.CharField(max_length=30, default="Und")
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre
