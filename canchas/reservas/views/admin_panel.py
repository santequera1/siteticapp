from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
from reservas.models import Negocio, Cancha, Reserva
from reservas.forms import NegocioForm, CanchaForm, ReservaAdminForm


def admin_login(request):
    """Login del panel de administración."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user and user.is_staff:
            login(request, user)
            return redirect('admin_dashboard')
        else:
            messages.error(request, 'Credenciales inválidas o no tienes permisos.')

    return render(request, 'reservas/admin_panel/login.html')


def admin_logout(request):
    logout(request)
    return redirect('admin_login')


@staff_member_required(login_url='/admin-panel/login/')
def admin_dashboard(request):
    """Dashboard principal del admin."""
    ahora = timezone.now()
    hoy = ahora.date()

    reservas_hoy = Reserva.objects.filter(fecha_inicio__date=hoy).exclude(estado='cancelada')
    reservas_pendientes = Reserva.objects.filter(estado='pendiente')
    canchas_activas = Cancha.objects.filter(is_active=True)

    # Ingresos del día
    ingresos_hoy = sum(
        r.total for r in reservas_hoy.filter(estado_pago__in=['pagado', 'abono_30'])
    )

    # Próximas reservas
    proximas = Reserva.objects.filter(
        fecha_inicio__gte=ahora,
        estado__in=['pendiente', 'confirmada']
    ).order_by('fecha_inicio')[:5]

    # Saludo
    hora = ahora.hour
    if hora < 12:
        greeting = 'Buenos dias'
    elif hora < 18:
        greeting = 'Buenas tardes'
    else:
        greeting = 'Buenas noches'

    return render(request, 'reservas/admin_panel/dashboard.html', {
        'reservas_hoy': reservas_hoy.count(),
        'reservas_pendientes': reservas_pendientes.count(),
        'canchas_activas': canchas_activas.count(),
        'ingresos_hoy': ingresos_hoy,
        'proximas': proximas,
        'greeting': greeting,
    })


# ===================== NEGOCIO =====================

@staff_member_required(login_url='/admin-panel/login/')
def negocio_edit(request):
    """Configuración del negocio."""
    negocio = Negocio.get_instance()

    if request.method == 'POST':
        form = NegocioForm(request.POST, request.FILES, instance=negocio)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración guardada.')
            return redirect('admin_negocio')
    else:
        form = NegocioForm(instance=negocio)

    return render(request, 'reservas/admin_panel/negocio_form.html', {
        'form': form,
    })


# ===================== CANCHAS CRUD =====================

@staff_member_required(login_url='/admin-panel/login/')
def cancha_admin_lista(request):
    """Lista de canchas (admin)."""
    canchas = Cancha.objects.all()
    return render(request, 'reservas/admin_panel/cancha_lista.html', {
        'canchas': canchas,
    })


@staff_member_required(login_url='/admin-panel/login/')
def cancha_admin_crear(request):
    """Crear cancha."""
    if request.method == 'POST':
        form = CanchaForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cancha creada exitosamente.')
            return redirect('admin_canchas')
    else:
        form = CanchaForm()

    return render(request, 'reservas/admin_panel/cancha_form.html', {
        'form': form,
        'titulo': 'Crear Cancha',
    })


@staff_member_required(login_url='/admin-panel/login/')
def cancha_admin_editar(request, pk):
    """Editar cancha."""
    cancha = get_object_or_404(Cancha, pk=pk)

    if request.method == 'POST':
        form = CanchaForm(request.POST, request.FILES, instance=cancha)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cancha actualizada.')
            return redirect('admin_canchas')
    else:
        form = CanchaForm(instance=cancha)

    return render(request, 'reservas/admin_panel/cancha_form.html', {
        'form': form,
        'cancha': cancha,
        'titulo': f'Editar {cancha.nombre}',
    })


@staff_member_required(login_url='/admin-panel/login/')
def cancha_admin_eliminar(request, pk):
    """Eliminar cancha."""
    cancha = get_object_or_404(Cancha, pk=pk)

    if request.method == 'POST':
        cancha.delete()
        messages.success(request, 'Cancha eliminada.')
        return redirect('admin_canchas')

    return render(request, 'reservas/admin_panel/cancha_confirm_delete.html', {
        'cancha': cancha,
    })


# ===================== RESERVAS ADMIN =====================

@staff_member_required(login_url='/admin-panel/login/')
def reserva_admin_lista(request):
    """Lista de reservas con filtros."""
    reservas = Reserva.objects.all().select_related('cancha')
    hoy = timezone.localdate()

    estado = request.GET.get('estado')
    if estado:
        reservas = reservas.filter(estado=estado)

    cancha_id = request.GET.get('cancha')
    if cancha_id:
        reservas = reservas.filter(cancha_id=cancha_id)

    # Rango rápido: hoy / ayer / semana / proximas / pasadas / fecha
    rango = request.GET.get('rango', '')
    fecha = request.GET.get('fecha', '')
    fecha_desde = request.GET.get('desde', '')
    fecha_hasta = request.GET.get('hasta', '')

    if rango == 'hoy':
        reservas = reservas.filter(fecha_inicio__date=hoy)
    elif rango == 'ayer':
        reservas = reservas.filter(fecha_inicio__date=hoy - timedelta(days=1))
    elif rango == 'manana':
        reservas = reservas.filter(fecha_inicio__date=hoy + timedelta(days=1))
    elif rango == 'semana':
        reservas = reservas.filter(
            fecha_inicio__date__gte=hoy,
            fecha_inicio__date__lte=hoy + timedelta(days=6),
        )
    elif rango == 'proximas':
        reservas = reservas.filter(fecha_inicio__gte=timezone.now())
    elif rango == 'pasadas':
        reservas = reservas.filter(fecha_inicio__lt=timezone.now())
    elif rango == 'personalizado':
        if fecha_desde:
            reservas = reservas.filter(fecha_inicio__date__gte=fecha_desde)
        if fecha_hasta:
            reservas = reservas.filter(fecha_inicio__date__lte=fecha_hasta)
    elif fecha:
        # compat con el filtro antiguo
        reservas = reservas.filter(fecha_inicio__date=fecha)

    canchas = Cancha.objects.all()

    return render(request, 'reservas/admin_panel/reserva_lista.html', {
        'reservas': reservas.order_by('-fecha_inicio')[:200],
        'total_count': reservas.count(),
        'canchas': canchas,
        'filtro_estado': estado,
        'filtro_cancha': cancha_id,
        'filtro_fecha': fecha,
        'filtro_rango': rango,
        'filtro_desde': fecha_desde,
        'filtro_hasta': fecha_hasta,
    })


@staff_member_required(login_url='/admin-panel/login/')
def reserva_admin_detalle(request, pk):
    """Detalle de una reserva."""
    reserva = get_object_or_404(Reserva, pk=pk)
    return render(request, 'reservas/admin_panel/reserva_detalle.html', {
        'reserva': reserva,
    })


@staff_member_required(login_url='/admin-panel/login/')
def reserva_admin_crear(request):
    """Admin crea una reserva."""
    if request.method == 'POST':
        form = ReservaAdminForm(request.POST)
        if form.is_valid():
            reserva = form.save(commit=False)
            reserva.estado = 'confirmada'
            reserva.save()
            messages.success(request, 'Reserva creada.')
            return redirect('admin_reservas')
    else:
        form = ReservaAdminForm()

    return render(request, 'reservas/admin_panel/reserva_form.html', {
        'form': form,
    })


@staff_member_required(login_url='/admin-panel/login/')
def reserva_cambiar_estado(request, pk, nuevo_estado):
    """Cambiar estado de una reserva."""
    reserva = get_object_or_404(Reserva, pk=pk)
    estados_validos = ['pendiente', 'confirmada', 'cancelada', 'finalizada']

    if nuevo_estado in estados_validos:
        reserva.estado = nuevo_estado
        reserva.save(update_fields=['estado', 'updated_at'])
        messages.success(request, f'Reserva {reserva.get_estado_display()}.')

    return redirect('admin_reserva_detalle', pk=pk)


@staff_member_required(login_url='/admin-panel/login/')
def admin_calendario(request):
    """Vista de calendario estilo AgendaPro."""
    canchas = Cancha.objects.filter(is_active=True)
    fecha_str = request.GET.get('fecha')

    if fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha = timezone.now().date()
    else:
        fecha = timezone.now().date()

    # Generar horas del día (según negocio o default 6-24)
    negocio = Negocio.objects.first()
    hora_inicio = 6
    hora_fin = 24
    if negocio:
        hora_inicio = negocio.horario_apertura.hour
        h_cierre = negocio.horario_cierre.hour
        hora_fin = h_cierre if h_cierre > 0 else 24

    horas = list(range(hora_inicio, hora_fin))

    # Obtener reservas del día
    reservas_dia = Reserva.objects.filter(
        fecha_inicio__date=fecha
    ).exclude(estado='cancelada').select_related('cancha')

    # Construir mapa de reservas por cancha y hora
    mapa = {}
    for cancha in canchas:
        mapa[cancha.pk] = {}

    for r in reservas_dia:
        hora = r.fecha_inicio.hour
        end_h = r.fecha_fin.hour if r.fecha_fin.hour > 0 else 24
        mapa[r.cancha_id][hora] = {
            'reserva': r,
            'rowspan': end_h - hora,
            'is_start': True,
        }
        # Marcar horas intermedias como ocupadas
        for h in range(hora + 1, end_h):
            mapa[r.cancha_id][h] = {'is_start': False}

    # Calcular fecha anterior y siguiente
    prev_fecha = (fecha - timedelta(days=1)).strftime('%Y-%m-%d')
    next_fecha = (fecha + timedelta(days=1)).strftime('%Y-%m-%d')

    return render(request, 'reservas/admin_panel/calendario.html', {
        'canchas': canchas,
        'fecha': fecha,
        'prev_fecha': prev_fecha,
        'next_fecha': next_fecha,
        'horas': horas,
        'mapa': mapa,
    })
