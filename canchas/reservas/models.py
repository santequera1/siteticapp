from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from datetime import datetime


class Negocio(models.Model):
    """Modelo singleton para la configuración del negocio."""
    nombre = models.CharField(max_length=200, default='Mi Centro Deportivo')
    descripcion = models.TextField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.TextField(blank=True)
    logo = models.ImageField(upload_to='negocio/', blank=True, null=True)
    horario_apertura = models.TimeField(default='06:00')
    horario_cierre = models.TimeField(default='22:00')

    class Meta:
        verbose_name = 'Negocio'
        verbose_name_plural = 'Negocio'

    def save(self, *args, **kwargs):
        if not self.pk and Negocio.objects.exists():
            raise ValidationError("Solo puede existir un registro de negocio.")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre

    @classmethod
    def get_instance(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance


TIPO_CANCHA_CHOICES = [
    ('futbol_5', 'Fútbol 5'),
    ('futbol_7', 'Fútbol 7'),
    ('futbol_8', 'Fútbol 8'),
    ('futbol_9', 'Fútbol 9'),
    ('futbol_11', 'Fútbol 11'),
]

SUPERFICIE_CHOICES = [
    ('sintetica', 'Sintética'),
    ('natural', 'Natural'),
    ('piso_duro', 'Piso duro'),
]


class Cancha(models.Model):
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPO_CANCHA_CHOICES, default='futbol_5')
    superficie = models.CharField(max_length=20, choices=SUPERFICIE_CHOICES, default='sintetica')
    capacidad = models.PositiveIntegerField(default=10, help_text='Jugadores por partido')
    precio_por_hora = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    imagen = models.ImageField(upload_to='canchas/', blank=True, null=True)
    caracteristicas = models.TextField(blank=True, help_text='Características separadas por línea')
    reglas = models.TextField(blank=True)
    horario_apertura = models.TimeField(default='06:00')
    horario_cierre = models.TimeField(default='22:00')
    es_techada = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cancha'
        verbose_name_plural = 'Canchas'
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"

    def get_caracteristicas_list(self):
        if not self.caracteristicas:
            return []
        return [c.strip() for c in self.caracteristicas.split('\n') if c.strip()]


ESTADO_RESERVA_CHOICES = [
    ('pendiente', 'Pendiente'),
    ('confirmada', 'Confirmada'),
    ('cancelada', 'Cancelada'),
    ('finalizada', 'Finalizada'),
]

TIPO_PAGO_CHOICES = [
    ('efectivo', 'Efectivo'),
    ('transferencia', 'Transferencia'),
    ('nequi', 'Nequi'),
    ('pse', 'PSE'),
    ('wompi', 'Wompi'),
]

ESTADO_PAGO_CHOICES = [
    ('pendiente', 'Pendiente'),
    ('abono_30', 'Abono 30%'),
    ('pagado', 'Pagado'),
]

DURACION_CHOICES = [
    (1, '1 hora'),
    (2, '2 horas'),
    (3, '3 horas'),
]


class Reserva(models.Model):
    cancha = models.ForeignKey(Cancha, on_delete=models.CASCADE, related_name='reservas')
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    duracion = models.PositiveIntegerField(choices=DURACION_CHOICES, default=1)

    # Cliente
    cliente_nombre = models.CharField(max_length=255)
    cliente_telefono = models.CharField(max_length=20, blank=True)
    cliente_email = models.CharField(max_length=255, blank=True)

    # Estado y pago
    estado = models.CharField(max_length=20, choices=ESTADO_RESERVA_CHOICES, default='pendiente')
    tipo_pago = models.CharField(max_length=20, choices=TIPO_PAGO_CHOICES, default='efectivo')
    estado_pago = models.CharField(max_length=20, choices=ESTADO_PAGO_CHOICES, default='pendiente')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    nota = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Reserva'
        verbose_name_plural = 'Reservas'
        ordering = ['-fecha_inicio']

    def clean(self):
        if isinstance(self.fecha_inicio, str):
            self.fecha_inicio = datetime.fromisoformat(self.fecha_inicio)
        if isinstance(self.fecha_fin, str):
            self.fecha_fin = datetime.fromisoformat(self.fecha_fin)

        if self.fecha_inicio and self.fecha_fin:
            if self.fecha_inicio.minute != 0 or self.fecha_fin.minute != 0:
                raise ValidationError("La hora debe ser en punto (por ejemplo: 10:00, 11:00).")

            if self.fecha_fin <= self.fecha_inicio:
                raise ValidationError("La fecha fin debe ser posterior a la fecha inicio.")

            reservas_existentes = Reserva.objects.filter(
                cancha=self.cancha,
                fecha_inicio__lt=self.fecha_fin,
                fecha_fin__gt=self.fecha_inicio
            ).exclude(pk=self.pk).exclude(estado='cancelada')

            if reservas_existentes.exists():
                raise ValidationError("Esta cancha ya está reservada en ese horario.")

    def save(self, *args, **kwargs):
        if not self.total and self.cancha and self.duracion:
            self.total = self.cancha.precio_por_hora * self.duracion
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cancha.nombre} - {self.cliente_nombre} ({self.fecha_inicio.strftime('%d/%m/%Y %H:%M')})"

    @property
    def monto_abono(self):
        return round(self.total * 30 / 100, 2)


# =====================================================================
# Reservas recurrentes (alquileres fijos: "todos los viernes 9pm-11pm")
# =====================================================================

DIA_SEMANA_CHOICES = [
    (0, 'Lunes'),
    (1, 'Martes'),
    (2, 'Miércoles'),
    (3, 'Jueves'),
    (4, 'Viernes'),
    (5, 'Sábado'),
    (6, 'Domingo'),
]

ESTADO_RECURRENTE_CHOICES = [
    ('activa', 'Activa'),
    ('pausada', 'Pausada'),
    ('cancelada', 'Cancelada'),
]


class ReservaRecurrente(models.Model):
    """Alquiler fijo recurrente. Ej: todos los viernes 9pm-11pm de marzo a diciembre."""
    cancha = models.ForeignKey(Cancha, on_delete=models.CASCADE, related_name='recurrentes')
    dia_semana = models.IntegerField(choices=DIA_SEMANA_CHOICES)
    hora_inicio = models.PositiveIntegerField(help_text='Hora de inicio (0-23 o 24-29 si cruza medianoche)')
    duracion = models.PositiveIntegerField(choices=DURACION_CHOICES, default=1)

    fecha_desde = models.DateField()
    fecha_hasta = models.DateField()

    cliente_nombre = models.CharField(max_length=255)
    cliente_telefono = models.CharField(max_length=20, blank=True)
    cliente_email = models.CharField(max_length=255, blank=True)

    precio_acordado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Si está vacío usa el precio normal de la cancha'
    )
    estado = models.CharField(max_length=15, choices=ESTADO_RECURRENTE_CHOICES, default='activa')
    nota = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Reserva recurrente'
        verbose_name_plural = 'Reservas recurrentes'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.cancha.nombre} · {self.get_dia_semana_display()} {self.hora_inicio:02d}:00 · {self.cliente_nombre}"

    def aplica_en(self, fecha):
        """True si esta recurrente afecta esa fecha concreta."""
        if self.estado != 'activa':
            return False
        if fecha < self.fecha_desde or fecha > self.fecha_hasta:
            return False
        if fecha.weekday() != self.dia_semana:
            return False
        if self.excepciones.filter(fecha=fecha).exists():
            return False
        return True

    @property
    def precio_efectivo(self):
        if self.precio_acordado is not None:
            return self.precio_acordado
        return self.cancha.precio_por_hora * self.duracion


class ReservaRecurrenteExcepcion(models.Model):
    """Fechas específicas en las que NO aplica una recurrente (ej: feriado, cancelación puntual)."""
    recurrente = models.ForeignKey(ReservaRecurrente, on_delete=models.CASCADE, related_name='excepciones')
    fecha = models.DateField()
    motivo = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('recurrente', 'fecha')
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.recurrente} · excepción {self.fecha}"


# =====================================================================
# POS — productos y ventas
# =====================================================================

CATEGORIA_PRODUCTO_CHOICES = [
    ('bebida', 'Bebida'),
    ('snack', 'Snack'),
    ('alquiler', 'Alquiler (guayos, etc.)'),
    ('servicio', 'Servicio'),
    ('otro', 'Otro'),
]


class Producto(models.Model):
    nombre = models.CharField(max_length=120)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_PRODUCTO_CHOICES, default='bebida')
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.IntegerField(
        null=True, blank=True,
        help_text='Dejar vacío para no controlar inventario'
    )
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['categoria', 'nombre']

    def __str__(self):
        return self.nombre


METODO_PAGO_VENTA = [
    ('efectivo', 'Efectivo'),
    ('transferencia', 'Transferencia'),
    ('nequi', 'Nequi'),
    ('tarjeta', 'Tarjeta'),
    ('otro', 'Otro'),
]


class Venta(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_VENTA, default='efectivo')
    reserva = models.ForeignKey(
        Reserva, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas',
        help_text='Asociar a una reserva (opcional)'
    )
    nota = models.TextField(blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ventas_registradas'
    )

    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha']

    def __str__(self):
        return f"Venta #{self.pk} · ${self.total}"

    def recalcular_total(self):
        self.total = sum((item.subtotal for item in self.items.all()), 0)
        self.save(update_fields=['total'])


class VentaItem(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, blank=True)
    nombre_snapshot = models.CharField(max_length=200, help_text='Nombre del producto al momento de la venta')
    cantidad = models.PositiveIntegerField(default=1)
    precio_unit = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.precio_unit * self.cantidad
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre_snapshot} x{self.cantidad}"
