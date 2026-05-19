from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
from reservas.models import Negocio, Cancha, Reserva, DURACION_CHOICES, TIPO_PAGO_CHOICES


def home(request):
    """Página principal del cliente."""
    canchas = Cancha.objects.filter(is_active=True)
    return render(request, 'reservas/client/home.html', {
        'canchas': canchas,
    })


def cancha_lista(request):
    """Lista de canchas disponibles."""
    canchas = Cancha.objects.filter(is_active=True)
    return render(request, 'reservas/client/cancha_lista.html', {
        'canchas': canchas,
    })


def cancha_detalle(request, pk):
    """Detalle de una cancha."""
    cancha = get_object_or_404(Cancha, pk=pk, is_active=True)
    return render(request, 'reservas/client/cancha_detalle.html', {
        'cancha': cancha,
    })


# ===================== FLUJO DE RESERVA =====================

def booking_step1(request):
    """Paso 1: Elegir cancha."""
    canchas = Cancha.objects.filter(is_active=True)

    if request.method == 'POST':
        cancha_id = request.POST.get('cancha_id')
        if cancha_id:
            request.session['booking'] = {'cancha_id': int(cancha_id)}
            return redirect('booking_step2')

    return render(request, 'reservas/client/booking/step1_cancha.html', {
        'canchas': canchas,
    })


def booking_step2(request):
    """Paso 2: Elegir fecha."""
    booking = request.session.get('booking')
    if not booking or 'cancha_id' not in booking:
        return redirect('booking_step1')

    cancha = get_object_or_404(Cancha, pk=booking['cancha_id'])

    if request.method == 'POST':
        fecha = request.POST.get('fecha')
        if fecha:
            booking['fecha'] = fecha
            request.session['booking'] = booking
            return redirect('booking_step3')

    return render(request, 'reservas/client/booking/step2_fecha.html', {
        'cancha': cancha,
    })


def booking_step3(request):
    """Paso 3: Elegir duración."""
    booking = request.session.get('booking')
    if not booking or 'fecha' not in booking:
        return redirect('booking_step1')

    cancha = get_object_or_404(Cancha, pk=booking['cancha_id'])

    if request.method == 'POST':
        duracion = request.POST.get('duracion')
        if duracion:
            booking['duracion'] = int(duracion)
            request.session['booking'] = booking
            return redirect('booking_step4')

    duraciones_con_precio = [
        (value, label, float(cancha.precio_por_hora * value))
        for value, label in DURACION_CHOICES
    ]

    return render(request, 'reservas/client/booking/step3_duracion.html', {
        'cancha': cancha,
        'duraciones_con_precio': duraciones_con_precio,
    })


def booking_step4(request):
    """Paso 4: Elegir horario disponible."""
    booking = request.session.get('booking')
    if not booking or 'duracion' not in booking:
        return redirect('booking_step1')

    cancha = get_object_or_404(Cancha, pk=booking['cancha_id'])
    fecha = datetime.strptime(booking['fecha'], '%Y-%m-%d').date()
    duracion = booking['duracion']

    # Calcular slots disponibles
    reservas_dia = Reserva.objects.filter(
        cancha=cancha,
        fecha_inicio__date=fecha,
    ).exclude(estado='cancelada')

    horas_ocupadas = set()
    for r in reservas_dia:
        hora = r.fecha_inicio.hour
        while hora < r.fecha_fin.hour:
            horas_ocupadas.add(hora)
            hora += 1

    apertura = cancha.horario_apertura.hour
    cierre = cancha.horario_cierre.hour
    slots = []

    # Si cierre es medianoche (0), tratar como 24
    cierre_h = cierre if cierre > 0 else 24

    for hora in range(apertura, cierre_h - duracion + 1):
        bloque_libre = all((hora + h) not in horas_ocupadas for h in range(duracion))
        slots.append({
            'hora': hora,
            'hora_inicio': f"{hora:02d}:00",
            'hora_fin': f"{hora + duracion:02d}:00",
            'precio': float(cancha.precio_por_hora * duracion),
            'disponible': bloque_libre,
        })

    if request.method == 'POST':
        hora_sel = request.POST.get('hora')
        if hora_sel:
            booking['hora'] = int(hora_sel)
            booking['total'] = float(cancha.precio_por_hora * duracion)
            request.session['booking'] = booking
            return redirect('booking_step5')

    return render(request, 'reservas/client/booking/step4_horario.html', {
        'cancha': cancha,
        'fecha': fecha,
        'duracion': duracion,
        'slots': slots,
    })


def booking_step5(request):
    """Paso 5: Resumen y datos del cliente."""
    booking = request.session.get('booking')
    if not booking or 'hora' not in booking:
        return redirect('booking_step1')

    cancha = get_object_or_404(Cancha, pk=booking['cancha_id'])
    fecha = datetime.strptime(booking['fecha'], '%Y-%m-%d').date()
    hora = booking['hora']
    duracion = booking['duracion']

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        email = request.POST.get('email', '').strip()
        nota = request.POST.get('nota', '').strip()

        if nombre and telefono:
            booking['nombre'] = nombre
            booking['telefono'] = telefono
            booking['email'] = email
            booking['nota'] = nota
            request.session['booking'] = booking
            return redirect('booking_step6')
        else:
            messages.error(request, 'Nombre y teléfono son obligatorios.')

    return render(request, 'reservas/client/booking/step5_resumen.html', {
        'cancha': cancha,
        'fecha': fecha,
        'hora_inicio': f"{hora:02d}:00",
        'hora_fin': f"{hora + duracion:02d}:00",
        'duracion': duracion,
        'total': booking['total'],
    })


def booking_step6(request):
    """Paso 6: Método de pago."""
    booking = request.session.get('booking')
    if not booking or 'nombre' not in booking:
        return redirect('booking_step1')

    cancha = get_object_or_404(Cancha, pk=booking['cancha_id'])
    total = booking['total']
    abono_30 = round(total * 0.3, 2)

    if request.method == 'POST':
        tipo_pago = request.POST.get('tipo_pago', 'efectivo')
        estado_pago = request.POST.get('estado_pago', 'pendiente')

        booking['tipo_pago'] = tipo_pago
        booking['estado_pago'] = estado_pago
        request.session['booking'] = booking
        return redirect('booking_confirmar')

    return render(request, 'reservas/client/booking/step6_pago.html', {
        'cancha': cancha,
        'total': total,
        'abono_30': abono_30,
        'tipos_pago': TIPO_PAGO_CHOICES,
    })


def booking_confirmar(request):
    """Paso final: Crear la reserva."""
    booking = request.session.get('booking')
    if not booking or 'tipo_pago' not in booking:
        return redirect('booking_step1')

    cancha = get_object_or_404(Cancha, pk=booking['cancha_id'])
    fecha = datetime.strptime(booking['fecha'], '%Y-%m-%d')
    hora = booking['hora']
    duracion = booking['duracion']

    fecha_inicio = timezone.make_aware(fecha.replace(hour=hora, minute=0, second=0))
    fecha_fin = fecha_inicio + timedelta(hours=duracion)

    try:
        reserva = Reserva(
            cancha=cancha,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            duracion=duracion,
            cliente_nombre=booking['nombre'],
            cliente_telefono=booking['telefono'],
            cliente_email=booking.get('email', ''),
            estado='pendiente',
            tipo_pago=booking['tipo_pago'],
            estado_pago=booking['estado_pago'],
            total=booking['total'],
            nota=booking.get('nota', ''),
        )
        reserva.save()

        # Limpiar sesión
        del request.session['booking']

        return render(request, 'reservas/client/booking/confirmacion.html', {
            'reserva': reserva,
        })
    except Exception as e:
        messages.error(request, f'Error al crear la reserva: {e}')
        return redirect('booking_step1')


def historial(request):
    """Historial de reservas por teléfono."""
    telefono = request.GET.get('telefono', '').strip()
    reservas = []

    if telefono:
        reservas = Reserva.objects.filter(
            cliente_telefono=telefono
        ).select_related('cancha').order_by('-fecha_inicio')

    return render(request, 'reservas/client/historial.html', {
        'telefono': telefono,
        'reservas': reservas,
    })
