import csv
import json
from decimal import Decimal
from datetime import date, datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Sum, Count, F, Q, DecimalField, IntegerField
from django.db.models.functions import Coalesce, ExtractHour
from django.utils import timezone

from reservas.models import (
    Producto, Venta, VentaItem, Cancha, Reserva,
    METODO_PAGO_VENTA, ReservaRecurrente,
)
from reservas.forms import ProductoForm


# =====================================================================
# PRODUCTOS
# =====================================================================

@staff_member_required(login_url='/admin-panel/login/')
def producto_lista(request):
    productos = Producto.objects.all().order_by('categoria', 'nombre')
    return render(request, 'reservas/admin_panel/producto_lista.html', {
        'productos': productos,
    })


@staff_member_required(login_url='/admin-panel/login/')
def producto_crear(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto creado.')
            return redirect('admin_productos')
    else:
        form = ProductoForm()
    return render(request, 'reservas/admin_panel/producto_form.html', {
        'form': form, 'titulo': 'Nuevo producto',
    })


@staff_member_required(login_url='/admin-panel/login/')
def producto_editar(request, pk):
    p = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=p)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto actualizado.')
            return redirect('admin_productos')
    else:
        form = ProductoForm(instance=p)
    return render(request, 'reservas/admin_panel/producto_form.html', {
        'form': form, 'producto': p, 'titulo': f'Editar {p.nombre}',
    })


@staff_member_required(login_url='/admin-panel/login/')
def producto_eliminar(request, pk):
    p = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        p.delete()
        messages.success(request, 'Producto eliminado.')
        return redirect('admin_productos')
    return render(request, 'reservas/admin_panel/producto_confirm_delete.html', {'producto': p})


# =====================================================================
# POS (caja)
# =====================================================================

@staff_member_required(login_url='/admin-panel/login/')
def pos(request):
    productos = Producto.objects.filter(is_active=True).order_by('categoria', 'nombre')
    return render(request, 'reservas/admin_panel/pos.html', {
        'productos': productos,
        'metodos_pago': METODO_PAGO_VENTA,
    })


@staff_member_required(login_url='/admin-panel/login/')
@require_POST
def pos_registrar(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    items = payload.get('items') or []
    if not items:
        return JsonResponse({'ok': False, 'error': 'No hay items en la venta'}, status=400)

    metodo_pago = payload.get('metodo_pago', 'efectivo')
    if metodo_pago not in {m[0] for m in METODO_PAGO_VENTA}:
        metodo_pago = 'efectivo'

    reserva_id = payload.get('reserva_id') or None
    reserva = None
    if reserva_id:
        try:
            reserva = Reserva.objects.get(pk=int(reserva_id))
        except (Reserva.DoesNotExist, ValueError, TypeError):
            reserva = None

    nota = (payload.get('nota') or '').strip()

    try:
        with transaction.atomic():
            venta = Venta.objects.create(
                metodo_pago=metodo_pago,
                reserva=reserva,
                nota=nota,
                usuario=request.user if request.user.is_authenticated else None,
                total=0,
            )
            for item in items:
                cantidad = int(item.get('cantidad', 1))
                if cantidad < 1:
                    continue
                producto = None
                pid = item.get('producto_id')
                if pid:
                    try:
                        producto = Producto.objects.get(pk=int(pid))
                    except (Producto.DoesNotExist, ValueError, TypeError):
                        producto = None
                nombre = (item.get('nombre') or (producto.nombre if producto else 'Item manual')).strip()
                precio_unit = Decimal(str(item.get('precio') or (producto.precio if producto else 0)))
                VentaItem.objects.create(
                    venta=venta,
                    producto=producto,
                    nombre_snapshot=nombre[:200],
                    cantidad=cantidad,
                    precio_unit=precio_unit,
                    subtotal=precio_unit * cantidad,
                )
                if producto and producto.stock is not None:
                    producto.stock = max(0, producto.stock - cantidad)
                    producto.save(update_fields=['stock'])
            venta.recalcular_total()
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'No se pudo registrar la venta: {e}'}, status=400)

    return JsonResponse({
        'ok': True,
        'venta': {
            'id': venta.pk,
            'total': float(venta.total),
            'metodo_pago': venta.metodo_pago,
        }
    })


# =====================================================================
# HISTORIAL DE VENTAS (con filtros y export CSV)
# =====================================================================

def _parse_date(s):
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _ventas_filtradas(request):
    """Aplica los filtros GET a Venta y retorna queryset + diccionario de filtros activos."""
    qs = Venta.objects.all().select_related('reserva__cancha', 'usuario').prefetch_related('items__producto')

    rango = request.GET.get('rango', 'todos')
    hoy = timezone.localdate()
    fecha_desde = _parse_date(request.GET.get('desde'))
    fecha_hasta = _parse_date(request.GET.get('hasta'))

    if rango == 'hoy':
        fecha_desde = fecha_hasta = hoy
    elif rango == 'ayer':
        fecha_desde = fecha_hasta = hoy - timedelta(days=1)
    elif rango == 'semana':
        fecha_desde = hoy - timedelta(days=6)
        fecha_hasta = hoy
    elif rango == 'mes':
        fecha_desde = hoy.replace(day=1)
        fecha_hasta = hoy

    if fecha_desde:
        qs = qs.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha__date__lte=fecha_hasta)

    metodo = request.GET.get('metodo')
    if metodo:
        qs = qs.filter(metodo_pago=metodo)

    producto_id = request.GET.get('producto')
    if producto_id:
        qs = qs.filter(items__producto_id=producto_id).distinct()

    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(reserva__cliente_nombre__icontains=q) |
            Q(reserva__cancha__nombre__icontains=q) |
            Q(nota__icontains=q) |
            Q(items__nombre_snapshot__icontains=q)
        ).distinct()

    return qs, {
        'rango': rango if rango else 'todos',
        'desde': fecha_desde.isoformat() if fecha_desde else '',
        'hasta': fecha_hasta.isoformat() if fecha_hasta else '',
        'metodo': metodo or '',
        'producto': producto_id or '',
        'q': q,
    }


@staff_member_required(login_url='/admin-panel/login/')
def venta_lista(request):
    qs, filtros = _ventas_filtradas(request)
    total_count = qs.count()
    total_monto = float(qs.aggregate(s=Coalesce(Sum('total'), Decimal('0')))['s'])
    ventas = qs.order_by('-fecha')[:200]

    productos = Producto.objects.filter(is_active=True).order_by('nombre')
    return render(request, 'reservas/admin_panel/venta_lista.html', {
        'ventas': ventas,
        'total_count': total_count,
        'total_monto': total_monto,
        'filtros': filtros,
        'metodos_pago': METODO_PAGO_VENTA,
        'productos': productos,
    })


@staff_member_required(login_url='/admin-panel/login/')
def venta_export_csv(request):
    qs, _ = _ventas_filtradas(request)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="ventas_{timezone.localdate().isoformat()}.csv"'
    response.write('﻿')  # BOM para Excel
    w = csv.writer(response, delimiter=';')
    w.writerow(['ID', 'Fecha', 'Hora', 'Total', 'Método', 'Reserva ID', 'Cancha', 'Cliente', 'Items', 'Nota'])
    for v in qs.order_by('-fecha'):
        items_str = ' | '.join(f"{it.cantidad}× {it.nombre_snapshot} (${it.subtotal:.0f})" for it in v.items.all())
        local = timezone.localtime(v.fecha)
        w.writerow([
            v.pk,
            local.strftime('%Y-%m-%d'),
            local.strftime('%H:%M'),
            f"{v.total:.0f}",
            v.get_metodo_pago_display(),
            v.reserva_id or '',
            v.reserva.cancha.nombre if v.reserva else '',
            v.reserva.cliente_nombre if v.reserva else '',
            items_str,
            (v.nota or '').replace('\n', ' '),
        ])
    return response


# =====================================================================
# REPORTES
# =====================================================================

def _rango_dates(request):
    """Determina (fecha_desde, fecha_hasta, label, rango_key) según GET params."""
    hoy = timezone.localdate()
    rango = request.GET.get('rango', 'mes')

    if rango == 'personalizado':
        fd = _parse_date(request.GET.get('desde')) or hoy
        fh = _parse_date(request.GET.get('hasta')) or hoy
        if fh < fd:
            fd, fh = fh, fd
        label = f"{fd.strftime('%d %b')} – {fh.strftime('%d %b %Y')}"
    elif rango == 'hoy' or rango == 'dia':
        fd = fh = hoy
        label = hoy.strftime('%d %b %Y')
        rango = 'hoy'
    elif rango == 'ayer':
        fd = fh = hoy - timedelta(days=1)
        label = fd.strftime('%d %b %Y')
    elif rango == 'semana':
        fd = hoy - timedelta(days=6)
        fh = hoy
        label = f"{fd.strftime('%d %b')} – {fh.strftime('%d %b %Y')}"
    elif rango == 'mes_anterior':
        primer_dia_mes_actual = hoy.replace(day=1)
        ultimo_mes_anterior = primer_dia_mes_actual - timedelta(days=1)
        fd = ultimo_mes_anterior.replace(day=1)
        fh = ultimo_mes_anterior
        label = fd.strftime('%B %Y')
    else:
        rango = 'mes'
        fd = hoy.replace(day=1)
        fh = hoy
        label = hoy.strftime('%B %Y')

    return fd, fh, label, rango


def _periodo_anterior(fd, fh):
    """Devuelve el período inmediatamente anterior con la misma duración."""
    dias = (fh - fd).days + 1
    fd_prev = fd - timedelta(days=dias)
    fh_prev = fd - timedelta(days=1)
    return fd_prev, fh_prev


def _pct_change(actual, anterior):
    if anterior == 0:
        return None if actual == 0 else 100.0
    return ((actual - anterior) / anterior) * 100.0


def _kpis_periodo(fd, fh, cancha_id=None):
    """Calcula KPIs financieros y operativos en un rango."""
    inicio_dt = timezone.make_aware(datetime.combine(fd, datetime.min.time()))
    fin_dt = timezone.make_aware(datetime.combine(fh + timedelta(days=1), datetime.min.time()))

    reservas = Reserva.objects.filter(
        fecha_inicio__gte=inicio_dt, fecha_inicio__lt=fin_dt,
    ).exclude(estado='cancelada')
    if cancha_id:
        reservas = reservas.filter(cancha_id=cancha_id)

    ventas = Venta.objects.filter(fecha__gte=inicio_dt, fecha__lt=fin_dt)
    if cancha_id:
        ventas = ventas.filter(reserva__cancha_id=cancha_id) | ventas.filter(reserva__isnull=True)

    ingreso_reservas = float(reservas.aggregate(s=Coalesce(Sum('total'), Decimal('0')))['s'])
    ingreso_ventas = float(ventas.aggregate(s=Coalesce(Sum('total'), Decimal('0')))['s'])
    n_reservas = reservas.count()
    n_ventas = ventas.count()
    horas_reservadas = int(reservas.aggregate(s=Coalesce(Sum('duracion'), 0))['s'])

    return {
        'ingreso_reservas': ingreso_reservas,
        'ingreso_ventas': ingreso_ventas,
        'total': ingreso_reservas + ingreso_ventas,
        'n_reservas': n_reservas,
        'n_ventas': n_ventas,
        'horas_reservadas': horas_reservadas,
        'ticket_promedio_pos': (ingreso_ventas / n_ventas) if n_ventas else 0,
        'ingreso_prom_reserva': (ingreso_reservas / n_reservas) if n_reservas else 0,
    }


def _slots_disponibles_periodo(fd, fh, cancha_id=None):
    """Estimación de slots-hora disponibles en el rango para cálculo de ocupación."""
    canchas = Cancha.objects.filter(is_active=True)
    if cancha_id:
        canchas = canchas.filter(pk=cancha_id)
    total = 0
    dias = (fh - fd).days + 1
    for c in canchas:
        apertura = c.horario_apertura.hour
        cierre = c.horario_cierre.hour
        if cierre == 0:
            cierre_h = 24
        elif cierre <= apertura:
            cierre_h = cierre + 24
        else:
            cierre_h = cierre
        total += (cierre_h - apertura) * dias
    return total


@staff_member_required(login_url='/admin-panel/login/')
def reportes(request):
    fd, fh, label, rango_key = _rango_dates(request)
    cancha_id = request.GET.get('cancha') or None
    if cancha_id:
        try:
            cancha_id = int(cancha_id)
        except (ValueError, TypeError):
            cancha_id = None

    inicio_dt = timezone.make_aware(datetime.combine(fd, datetime.min.time()))
    fin_dt = timezone.make_aware(datetime.combine(fh + timedelta(days=1), datetime.min.time()))

    # KPIs principales y comparativos
    kpis = _kpis_periodo(fd, fh, cancha_id)
    fd_prev, fh_prev = _periodo_anterior(fd, fh)
    kpis_prev = _kpis_periodo(fd_prev, fh_prev, cancha_id)

    # Ocupación
    slots_dispon = _slots_disponibles_periodo(fd, fh, cancha_id)
    ocupacion_pct = (kpis['horas_reservadas'] / slots_dispon * 100) if slots_dispon else 0

    # Tendencias (% change)
    trend = {
        'total': _pct_change(kpis['total'], kpis_prev['total']),
        'ingreso_reservas': _pct_change(kpis['ingreso_reservas'], kpis_prev['ingreso_reservas']),
        'ingreso_ventas': _pct_change(kpis['ingreso_ventas'], kpis_prev['ingreso_ventas']),
        'n_reservas': _pct_change(kpis['n_reservas'], kpis_prev['n_reservas']),
        'n_ventas': _pct_change(kpis['n_ventas'], kpis_prev['n_ventas']),
    }

    # Queryset base con filtro de cancha
    reservas = Reserva.objects.filter(
        fecha_inicio__gte=inicio_dt, fecha_inicio__lt=fin_dt,
    ).exclude(estado='cancelada').select_related('cancha')
    if cancha_id:
        reservas = reservas.filter(cancha_id=cancha_id)

    ventas = Venta.objects.filter(fecha__gte=inicio_dt, fecha__lt=fin_dt).prefetch_related('items__producto')

    # Ingresos por cancha
    por_cancha_qs = reservas.values('cancha__nombre').annotate(
        ingreso=Coalesce(Sum('total'), Decimal('0')),
        n=Count('id'),
    ).order_by('-ingreso')
    por_cancha = [
        {'nombre': r['cancha__nombre'], 'ingreso': float(r['ingreso'] or 0), 'n': int(r['n'] or 0)}
        for r in por_cancha_qs
    ]
    max_cancha = max((c['ingreso'] for c in por_cancha), default=0)
    for c in por_cancha:
        c['pct'] = (c['ingreso'] / max_cancha * 100) if max_cancha else 0

    # Productos y categorías
    items_qs = VentaItem.objects.filter(
        venta__fecha__gte=inicio_dt, venta__fecha__lt=fin_dt,
    ).select_related('producto', 'venta')
    if cancha_id:
        items_qs = items_qs.filter(venta__reserva__cancha_id=cancha_id) | items_qs.filter(venta__reserva__isnull=True)

    por_producto_agg = {}
    por_categoria_agg = {}
    productos_vendidos_ids = set()
    for it in items_qs:
        key = it.producto_id or it.nombre_snapshot
        if key not in por_producto_agg:
            por_producto_agg[key] = {'nombre': it.nombre_snapshot, 'ingreso': 0.0, 'cantidad': 0}
        por_producto_agg[key]['ingreso'] += float(it.subtotal)
        por_producto_agg[key]['cantidad'] += it.cantidad
        cat = it.producto.get_categoria_display() if it.producto else 'Otro'
        por_categoria_agg[cat] = por_categoria_agg.get(cat, 0.0) + float(it.subtotal)
        if it.producto_id:
            productos_vendidos_ids.add(it.producto_id)

    por_producto = sorted(por_producto_agg.values(), key=lambda x: -x['ingreso'])
    max_prod = max((p['ingreso'] for p in por_producto), default=0)
    for p in por_producto:
        p['pct'] = (p['ingreso'] / max_prod * 100) if max_prod else 0

    por_categoria = sorted(
        ({'nombre': k, 'ingreso': v} for k, v in por_categoria_agg.items()),
        key=lambda x: -x['ingreso']
    )
    max_cat = max((c['ingreso'] for c in por_categoria), default=0)
    for c in por_categoria:
        c['pct'] = (c['ingreso'] / max_cat * 100) if max_cat else 0

    # Métodos de pago
    metodos_qs = ventas.values('metodo_pago').annotate(s=Sum('total'), n=Count('id')).order_by('-s')
    metodos = [
        {'metodo': r['metodo_pago'], 'ingreso': float(r['s'] or 0), 'n': int(r['n'] or 0)}
        for r in metodos_qs
    ]
    max_met = max((m['ingreso'] for m in metodos), default=0)
    for m in metodos:
        m['pct'] = (m['ingreso'] / max_met * 100) if max_met else 0

    # Ventas POS por hora del día (0-23)
    ventas_por_hora = [{'hora': h, 'monto': 0.0, 'n': 0} for h in range(24)]
    for v in ventas:
        h = timezone.localtime(v.fecha).hour
        ventas_por_hora[h]['monto'] += float(v.total)
        ventas_por_hora[h]['n'] += 1
    max_h_ventas = max((x['monto'] for x in ventas_por_hora), default=0)
    for x in ventas_por_hora:
        x['pct'] = (x['monto'] / max_h_ventas * 100) if max_h_ventas else 0
    # Solo mostrar horas con actividad o el rango operativo (6-23)
    ventas_por_hora_show = [x for x in ventas_por_hora if x['n'] > 0 or (6 <= x['hora'] <= 23)]

    # Horarios más reservados
    horarios_agg = {}
    for r in reservas:
        h = timezone.localtime(r.fecha_inicio).hour
        for offset in range(r.duracion):
            hh = (h + offset) % 24
            horarios_agg[hh] = horarios_agg.get(hh, 0) + 1
    horarios_top = sorted(
        ({'hora': h, 'n': n} for h, n in horarios_agg.items()),
        key=lambda x: -x['n']
    )[:10]
    max_horario = max((x['n'] for x in horarios_top), default=0)
    for x in horarios_top:
        x['pct'] = (x['n'] / max_horario * 100) if max_horario else 0

    # Productos sin movimiento (activos pero sin venta en el período)
    sin_movimiento = Producto.objects.filter(
        is_active=True,
    ).exclude(pk__in=productos_vendidos_ids).order_by('categoria', 'nombre')

    # Cierre de caja del día (solo HOY)
    hoy = timezone.localdate()
    hoy_inicio = timezone.make_aware(datetime.combine(hoy, datetime.min.time()))
    hoy_fin = hoy_inicio + timedelta(days=1)
    cierre_qs = Venta.objects.filter(fecha__gte=hoy_inicio, fecha__lt=hoy_fin)
    cierre_metodos_qs = cierre_qs.values('metodo_pago').annotate(s=Sum('total'), n=Count('id'))
    cierre_metodos = [
        {'metodo': r['metodo_pago'], 'ingreso': float(r['s'] or 0), 'n': int(r['n'] or 0)}
        for r in cierre_metodos_qs
    ]
    cierre_total = float(cierre_qs.aggregate(s=Coalesce(Sum('total'), Decimal('0')))['s'])
    cierre_count = cierre_qs.count()
    cierre_reservas = Reserva.objects.filter(
        fecha_inicio__gte=hoy_inicio, fecha_inicio__lt=hoy_fin,
        estado_pago__in=['pagado', 'abono_30'],
    ).exclude(estado='cancelada')
    cierre_ingreso_reservas = float(cierre_reservas.aggregate(s=Coalesce(Sum('total'), Decimal('0')))['s'])
    cierre_n_reservas = cierre_reservas.count()

    canchas = Cancha.objects.all().order_by('nombre')

    return render(request, 'reservas/admin_panel/reportes.html', {
        'rango': rango_key,
        'rango_label': label,
        'fecha_desde': fd,
        'fecha_hasta': fh,
        'cancha_id': cancha_id,
        'canchas': canchas,

        'kpis': kpis,
        'kpis_prev': kpis_prev,
        'trend': trend,
        'ocupacion_pct': ocupacion_pct,
        'horas_reservadas': kpis['horas_reservadas'],
        'horas_disponibles': slots_dispon,

        'por_cancha': por_cancha,
        'por_producto': por_producto,
        'por_categoria': por_categoria,
        'metodos_pago': metodos,

        'ventas_por_hora': ventas_por_hora_show,
        'horarios_top': horarios_top,
        'sin_movimiento': sin_movimiento,

        'cierre_metodos': cierre_metodos,
        'cierre_total': cierre_total,
        'cierre_count': cierre_count,
        'cierre_ingreso_reservas': cierre_ingreso_reservas,
        'cierre_n_reservas': cierre_n_reservas,
    })
