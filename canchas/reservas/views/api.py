import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta, time
from reservas.models import Cancha, Reserva, ReservaRecurrente, TIPO_PAGO_CHOICES


def obtener_reservas(request):
    """API: todos los eventos para FullCalendar (admin)."""
    reservas = Reserva.objects.exclude(estado='cancelada').select_related('cancha')

    colores = {
        'pendiente': '#f59e0b',
        'confirmada': '#22c55e',
        'cancelada': '#ef4444',
        'finalizada': '#6b7280',
    }

    eventos = []
    for reserva in reservas:
        eventos.append({
            'id': reserva.id,
            'title': f"{reserva.cancha.nombre} - {reserva.cliente_nombre}",
            'start': reserva.fecha_inicio.strftime('%Y-%m-%dT%H:%M:%S'),
            'end': reserva.fecha_fin.strftime('%Y-%m-%dT%H:%M:%S'),
            'color': colores.get(reserva.estado, '#6b7280'),
            'extendedProps': {
                'cancha': reserva.cancha.nombre,
                'cliente': reserva.cliente_nombre,
                'telefono': reserva.cliente_telefono,
                'estado': reserva.get_estado_display(),
                'estado_pago': reserva.get_estado_pago_display(),
                'total': str(reserva.total),
            }
        })

    return JsonResponse(eventos, safe=False)


def reservas_por_dia(request, fecha):
    """API: reservas de un día específico (admin)."""
    reservas = Reserva.objects.filter(
        fecha_inicio__date=fecha
    ).exclude(estado='cancelada').order_by('fecha_inicio').select_related('cancha')

    data = [
        {
            'id': r.id,
            'cancha': r.cancha.nombre,
            'hora_inicio': r.fecha_inicio.strftime('%H:%M'),
            'hora_fin': r.fecha_fin.strftime('%H:%M'),
            'cliente': r.cliente_nombre,
            'telefono': r.cliente_telefono,
            'estado': r.estado,
            'estado_display': r.get_estado_display(),
            'nota': r.nota or '',
        }
        for r in reservas
    ]

    return JsonResponse({'reservas': data})


def api_disponibilidad(request):
    """API legacy: horarios disponibles para una cancha en una fecha con duración dada."""
    cancha_id = request.GET.get('cancha_id')
    fecha_str = request.GET.get('fecha')
    duracion = int(request.GET.get('duracion', 1))

    if not cancha_id or not fecha_str:
        return JsonResponse({'error': 'cancha_id y fecha son requeridos'}, status=400)

    try:
        cancha = Cancha.objects.get(pk=cancha_id, is_active=True)
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except (Cancha.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Cancha o fecha inválida'}, status=400)

    apertura, cierre_h = _court_hours(cancha)
    occupied = _occupied_hours_offset(cancha, fecha, apertura, cierre_h)

    slots = []
    for offset in range(apertura, cierre_h - duracion + 1):
        bloque_libre = all((offset + h) not in occupied for h in range(duracion))
        slots.append({
            'hora_inicio': f"{offset % 24:02d}:00",
            'hora_fin': f"{(offset + duracion) % 24:02d}:00",
            'disponible': bloque_libre,
            'precio': float(cancha.precio_por_hora * duracion),
        })

    return JsonResponse({
        'cancha': cancha.nombre,
        'fecha': fecha_str,
        'duracion': duracion,
        'slots': slots,
    })


# ====================================================================
# Helpers
# ====================================================================

def _court_hours(cancha):
    """Devuelve (apertura, cierre_h) en offset de horas desde la medianoche del día."""
    apertura = cancha.horario_apertura.hour
    cierre = cancha.horario_cierre.hour
    if cierre == 0:
        cierre_h = 24
    elif cierre <= apertura:
        # cruza medianoche
        cierre_h = cierre + 24
    else:
        cierre_h = cierre
    return apertura, cierre_h


def _occupied_hours_offset(cancha, fecha, apertura, cierre_h):
    """Devuelve un set de offsets de hora (relativos a medianoche del día) ocupados.

    Considera reservas que empiezan ese día, reservas que empezaron el día anterior
    y se extienden a la madrugada de este, y reservas recurrentes que apliquen.
    """
    inicio_ventana = timezone.make_aware(datetime.combine(fecha, time.min))
    fin_ventana = inicio_ventana + timedelta(hours=cierre_h)

    reservas = Reserva.objects.filter(
        cancha=cancha,
        fecha_inicio__lt=fin_ventana,
        fecha_fin__gt=inicio_ventana,
    ).exclude(estado='cancelada')

    occupied = set()
    for r in reservas:
        local_inicio = timezone.localtime(r.fecha_inicio)
        local_fin = timezone.localtime(r.fecha_fin)
        offset_inicio = int((local_inicio - timezone.localtime(inicio_ventana)).total_seconds() // 3600)
        offset_fin = int((local_fin - timezone.localtime(inicio_ventana)).total_seconds() // 3600)
        offset_inicio = max(offset_inicio, apertura)
        offset_fin = min(offset_fin, cierre_h)
        for h in range(offset_inicio, offset_fin):
            occupied.add(h)

    # Recurrentes activas que apliquen al día/cancha
    recurrentes = ReservaRecurrente.objects.filter(
        cancha=cancha,
        estado='activa',
        dia_semana=fecha.weekday(),
        fecha_desde__lte=fecha,
        fecha_hasta__gte=fecha,
    )
    for rec in recurrentes:
        if rec.excepciones.filter(fecha=fecha).exists():
            continue
        for h in range(rec.hora_inicio, rec.hora_inicio + rec.duracion):
            occupied.add(h)
    return occupied


def _hay_conflicto_recurrente(cancha, fecha, hora_offset, duracion):
    """True si una recurrente activa choca con [hora_offset, hora_offset+duracion) en esa fecha."""
    recurrentes = ReservaRecurrente.objects.filter(
        cancha=cancha,
        estado='activa',
        dia_semana=fecha.weekday(),
        fecha_desde__lte=fecha,
        fecha_hasta__gte=fecha,
    )
    for rec in recurrentes:
        if rec.excepciones.filter(fecha=fecha).exists():
            continue
        # Solapamiento de [rec.hora_inicio, rec.hora_inicio+rec.duracion) con [hora_offset, hora_offset+duracion)
        if rec.hora_inicio < hora_offset + duracion and (rec.hora_inicio + rec.duracion) > hora_offset:
            return True
    return False


# ====================================================================
# Nuevas APIs para landing con calendario interactivo
# ====================================================================

@require_GET
def disponibilidad_dia(request):
    """Devuelve el estado de cada hora para TODAS las canchas en un día.

    GET /api/disponibilidad-dia/?fecha=2026-05-17&duracion=1

    Los slots usan offset (0-29). Para canchas que cierran después de medianoche,
    `hora` puede ser >= 24 (significa madrugada del día siguiente). El cliente
    formatea con `hora % 24` para mostrar.
    """
    fecha_str = request.GET.get('fecha')
    try:
        duracion = int(request.GET.get('duracion', 1))
    except ValueError:
        duracion = 1
    duracion = max(1, min(duracion, 6))

    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else timezone.localdate()
    except ValueError:
        return JsonResponse({'error': 'fecha inválida (YYYY-MM-DD)'}, status=400)

    canchas = list(Cancha.objects.filter(is_active=True).order_by('nombre'))

    ahora_local = timezone.localtime()
    hoy_local = ahora_local.date()
    hora_actual = ahora_local.hour

    data_canchas = []
    for c in canchas:
        apertura, cierre_h = _court_hours(c)
        occupied = _occupied_hours_offset(c, fecha, apertura, cierre_h)

        slots = []
        for offset in range(apertura, cierre_h):
            # ¿Bloque de la duración completa cabe y está libre?
            cabe = offset + duracion <= cierre_h
            libre = cabe and all((offset + h) not in occupied for h in range(duracion))

            # ¿Está en el pasado?
            pasado = False
            if fecha < hoy_local:
                pasado = True
            elif fecha == hoy_local and offset < hora_actual:
                pasado = True

            if pasado:
                estado = 'pasado'
            elif offset in occupied:
                estado = 'ocupado'
            elif not libre:
                estado = 'parcial'
            else:
                estado = 'disponible'

            slots.append({
                'hora': offset,
                'hora_label': f"{offset % 24:02d}:00",
                'hora_fin_label': f"{(offset + duracion) % 24:02d}:00",
                'estado': estado,
                'precio': float(c.precio_por_hora * duracion),
            })

        data_canchas.append({
            'id': c.pk,
            'nombre': c.nombre,
            'tipo': c.get_tipo_display(),
            'superficie': c.get_superficie_display(),
            'capacidad': c.capacidad,
            'precio_hora': float(c.precio_por_hora),
            'es_techada': c.es_techada,
            'imagen': c.imagen.url if c.imagen else '',
            'slots': slots,
        })

    return JsonResponse({
        'fecha': fecha.isoformat(),
        'duracion': duracion,
        'canchas': data_canchas,
    })


@require_POST
@csrf_protect
def booking_create(request):
    """Crea una reserva en un único POST desde la landing.

    Body JSON:
      {
        "cancha_id": 1,
        "fecha": "2026-05-17",
        "hora": 19,          # offset desde medianoche; puede ser >=24 si cruza medianoche
        "duracion": 2,
        "nombre": "Juan", "telefono": "300...", "email": "",
        "tipo_pago": "efectivo", "estado_pago": "pendiente",
        "nota": ""
      }
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    required = ['cancha_id', 'fecha', 'hora', 'duracion', 'nombre', 'telefono']
    faltantes = [k for k in required if str(payload.get(k, '')).strip() == '']
    if faltantes:
        return JsonResponse({'ok': False, 'error': f'Faltan campos: {", ".join(faltantes)}'}, status=400)

    try:
        cancha = Cancha.objects.get(pk=int(payload['cancha_id']), is_active=True)
    except (Cancha.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Cancha no encontrada'}, status=404)

    try:
        fecha = datetime.strptime(payload['fecha'], '%Y-%m-%d').date()
        hora_offset = int(payload['hora'])
        duracion = int(payload['duracion'])
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Fecha, hora o duración inválida'}, status=400)

    if duracion not in (1, 2, 3):
        return JsonResponse({'ok': False, 'error': 'La duración debe ser 1, 2 o 3 horas'}, status=400)

    apertura, cierre_h = _court_hours(cancha)
    if hora_offset < apertura or (hora_offset + duracion) > cierre_h:
        return JsonResponse({'ok': False, 'error': 'El horario está fuera del horario de la cancha'}, status=400)

    tipos_validos = {t[0] for t in TIPO_PAGO_CHOICES}
    tipo_pago = payload.get('tipo_pago', 'efectivo')
    if tipo_pago not in tipos_validos:
        tipo_pago = 'efectivo'

    estado_pago = payload.get('estado_pago', 'pendiente')
    if estado_pago not in {'pendiente', 'abono_30', 'pagado'}:
        estado_pago = 'pendiente'

    # Construir datetime a partir del offset (que puede pasar de 23h)
    naive_inicio = datetime.combine(fecha, time.min) + timedelta(hours=hora_offset)
    fecha_inicio = timezone.make_aware(naive_inicio)
    fecha_fin = fecha_inicio + timedelta(hours=duracion)

    if fecha_inicio < timezone.now():
        return JsonResponse({'ok': False, 'error': 'No puedes reservar en el pasado'}, status=400)

    try:
        with transaction.atomic():
            conflicto = Reserva.objects.select_for_update().filter(
                cancha=cancha,
                fecha_inicio__lt=fecha_fin,
                fecha_fin__gt=fecha_inicio,
            ).exclude(estado='cancelada').exists()
            if conflicto or _hay_conflicto_recurrente(cancha, fecha, hora_offset, duracion):
                return JsonResponse(
                    {'ok': False, 'error': 'Ese horario ya fue tomado. Refresca para ver la disponibilidad actual.'},
                    status=409,
                )

            reserva = Reserva(
                cancha=cancha,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                duracion=duracion,
                cliente_nombre=str(payload['nombre']).strip()[:255],
                cliente_telefono=str(payload['telefono']).strip()[:20],
                cliente_email=str(payload.get('email', '')).strip()[:255],
                estado='pendiente',
                tipo_pago=tipo_pago,
                estado_pago=estado_pago,
                total=cancha.precio_por_hora * duracion,
                nota=str(payload.get('nota', '')).strip() or None,
            )
            reserva.save()
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'No se pudo crear la reserva: {e}'}, status=400)

    return JsonResponse({
        'ok': True,
        'reserva': {
            'id': reserva.id,
            'cancha': cancha.nombre,
            'fecha': fecha.isoformat(),
            'hora_inicio': fecha_inicio.strftime('%H:%M'),
            'hora_fin': fecha_fin.strftime('%H:%M'),
            'duracion': duracion,
            'total': float(reserva.total),
            'estado': reserva.estado,
            'tipo_pago': reserva.tipo_pago,
        },
    })
