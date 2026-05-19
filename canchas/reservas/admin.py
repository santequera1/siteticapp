from django.contrib import admin
from .models import Negocio, Cancha, Reserva


@admin.register(Negocio)
class NegocioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'telefono', 'email']


@admin.register(Cancha)
class CanchaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo', 'precio_por_hora', 'is_active']
    list_filter = ['tipo', 'is_active']


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ['cancha', 'cliente_nombre', 'fecha_inicio', 'estado', 'estado_pago', 'total']
    list_filter = ['estado', 'estado_pago', 'cancha']
    search_fields = ['cliente_nombre', 'cliente_telefono']
