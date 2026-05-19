from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Q

from reservas.models import Guayo, AlquilerGuayo, Cancha, Reserva
from reservas.forms import GuayoForm, AlquilerGuayoForm


# ===================== INVENTARIO =====================

@staff_member_required(login_url='/admin-panel/login/')
def lista(request):
    qs = Guayo.objects.all()
    estado = request.GET.get('estado', '')
    talla = request.GET.get('talla', '')
    q = (request.GET.get('q') or '').strip()
    if estado:
        qs = qs.filter(estado=estado)
    if talla:
        try:
            qs = qs.filter(talla=int(talla))
        except ValueError:
            pass
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(color__icontains=q) | Q(marca__icontains=q))

    # Stats por estado
    stats = {
        'total': Guayo.objects.count(),
        'disponibles': Guayo.objects.filter(estado='disponible').count(),
        'alquilados': Guayo.objects.filter(estado='alquilado').count(),
        'mantenimiento': Guayo.objects.filter(estado='mantenimiento').count(),
    }
    tallas_disponibles = sorted(Guayo.objects.values_list('talla', flat=True).distinct())

    return render(request, 'reservas/admin_panel/guayo_lista.html', {
        'guayos': qs.order_by('talla', 'color'),
        'filtro_estado': estado,
        'filtro_talla': talla,
        'filtro_q': q,
        'stats': stats,
        'tallas': tallas_disponibles,
    })


@staff_member_required(login_url='/admin-panel/login/')
def crear(request):
    if request.method == 'POST':
        form = GuayoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Par de guayos agregado al inventario.')
            return redirect('admin_guayos')
    else:
        # Sugerir código auto-incremental
        last = Guayo.objects.order_by('-id').first()
        next_num = (last.id if last else 0) + 1
        form = GuayoForm(initial={'codigo': f'G-{next_num:02d}', 'precio_alquiler': 15000})
    return render(request, 'reservas/admin_panel/guayo_form.html', {
        'form': form, 'titulo': 'Nuevo par de guayos',
    })


@staff_member_required(login_url='/admin-panel/login/')
def editar(request, pk):
    g = get_object_or_404(Guayo, pk=pk)
    if request.method == 'POST':
        form = GuayoForm(request.POST, instance=g)
        if form.is_valid():
            form.save()
            messages.success(request, 'Par actualizado.')
            return redirect('admin_guayos')
    else:
        form = GuayoForm(instance=g)
    return render(request, 'reservas/admin_panel/guayo_form.html', {
        'form': form, 'guayo': g, 'titulo': f'Editar {g.codigo}',
    })


@staff_member_required(login_url='/admin-panel/login/')
def eliminar(request, pk):
    g = get_object_or_404(Guayo, pk=pk)
    if request.method == 'POST':
        g.delete()
        messages.success(request, 'Par eliminado.')
        return redirect('admin_guayos')
    return render(request, 'reservas/admin_panel/guayo_confirm_delete.html', {'guayo': g})


# ===================== ALQUILERES =====================

@staff_member_required(login_url='/admin-panel/login/')
def alquileres(request):
    qs = AlquilerGuayo.objects.select_related('guayo', 'cancha', 'reserva__cancha').all()
    estado = request.GET.get('estado', 'activo')
    if estado:
        qs = qs.filter(estado=estado)
    return render(request, 'reservas/admin_panel/alquiler_guayo_lista.html', {
        'alquileres': qs.order_by('-fecha_alquiler')[:200],
        'filtro_estado': estado,
        'activos_count': AlquilerGuayo.objects.filter(estado='activo').count(),
        'devueltos_count': AlquilerGuayo.objects.filter(estado='devuelto').count(),
    })


@staff_member_required(login_url='/admin-panel/login/')
def alquilar(request):
    if request.method == 'POST':
        form = AlquilerGuayoForm(request.POST)
        if form.is_valid():
            alq = form.save(commit=False)
            alq.usuario = request.user if request.user.is_authenticated else None
            if not alq.precio:
                alq.precio = alq.guayo.precio_alquiler
            # Si viene de una reserva, copia la cancha
            if alq.reserva and not alq.cancha:
                alq.cancha = alq.reserva.cancha
            alq.save()
            # Marca el guayo como alquilado
            alq.guayo.estado = 'alquilado'
            alq.guayo.save(update_fields=['estado'])
            messages.success(request, f'Alquiler #{alq.pk} registrado.')
            return redirect('admin_alquileres_guayos')
    else:
        form = AlquilerGuayoForm()
    return render(request, 'reservas/admin_panel/alquiler_guayo_form.html', {
        'form': form,
    })


@staff_member_required(login_url='/admin-panel/login/')
def devolver(request, pk):
    alq = get_object_or_404(AlquilerGuayo, pk=pk)
    if alq.estado == 'activo':
        alq.marcar_devuelto()
        messages.success(request, f'Devolución registrada para {alq.guayo}.')
    return redirect('admin_alquileres_guayos')


@staff_member_required(login_url='/admin-panel/login/')
def marcar_perdido(request, pk):
    alq = get_object_or_404(AlquilerGuayo, pk=pk)
    if alq.estado == 'activo':
        alq.estado = 'perdido'
        alq.save(update_fields=['estado'])
        # El guayo queda fuera de circulación
        alq.guayo.estado = 'dado_baja'
        alq.guayo.save(update_fields=['estado'])
        messages.success(request, 'Marcado como no devuelto.')
    return redirect('admin_alquileres_guayos')
