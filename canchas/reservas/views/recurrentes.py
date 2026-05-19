from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from datetime import date, datetime

from reservas.models import (
    ReservaRecurrente, ReservaRecurrenteExcepcion, Cancha,
)
from reservas.forms import ReservaRecurrenteForm


@staff_member_required(login_url='/admin-panel/login/')
def lista(request):
    qs = ReservaRecurrente.objects.select_related('cancha').order_by('-estado', 'dia_semana', 'hora_inicio')
    estado = request.GET.get('estado')
    if estado:
        qs = qs.filter(estado=estado)
    cancha_id = request.GET.get('cancha')
    if cancha_id:
        qs = qs.filter(cancha_id=cancha_id)
    return render(request, 'reservas/admin_panel/recurrente_lista.html', {
        'recurrentes': qs,
        'canchas': Cancha.objects.all(),
        'filtro_estado': estado,
        'filtro_cancha': cancha_id,
    })


@staff_member_required(login_url='/admin-panel/login/')
def crear(request):
    if request.method == 'POST':
        form = ReservaRecurrenteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Reserva recurrente creada.')
            return redirect('admin_recurrentes')
    else:
        form = ReservaRecurrenteForm()
    return render(request, 'reservas/admin_panel/recurrente_form.html', {
        'form': form,
        'titulo': 'Nueva reserva recurrente',
    })


@staff_member_required(login_url='/admin-panel/login/')
def editar(request, pk):
    rec = get_object_or_404(ReservaRecurrente, pk=pk)
    if request.method == 'POST':
        form = ReservaRecurrenteForm(request.POST, instance=rec)
        if form.is_valid():
            form.save()
            messages.success(request, 'Reserva recurrente actualizada.')
            return redirect('admin_recurrentes')
    else:
        form = ReservaRecurrenteForm(instance=rec)
    return render(request, 'reservas/admin_panel/recurrente_form.html', {
        'form': form,
        'recurrente': rec,
        'excepciones': rec.excepciones.all(),
        'titulo': f'Editar recurrente · {rec.cancha.nombre}',
    })


@staff_member_required(login_url='/admin-panel/login/')
def eliminar(request, pk):
    rec = get_object_or_404(ReservaRecurrente, pk=pk)
    if request.method == 'POST':
        rec.delete()
        messages.success(request, 'Reserva recurrente eliminada.')
        return redirect('admin_recurrentes')
    return render(request, 'reservas/admin_panel/recurrente_confirm_delete.html', {
        'recurrente': rec,
    })


@staff_member_required(login_url='/admin-panel/login/')
def cambiar_estado(request, pk, nuevo_estado):
    rec = get_object_or_404(ReservaRecurrente, pk=pk)
    if nuevo_estado in ('activa', 'pausada', 'cancelada'):
        rec.estado = nuevo_estado
        rec.save(update_fields=['estado', 'updated_at'])
        messages.success(request, f'Estado cambiado a {rec.get_estado_display()}.')
    return redirect('admin_recurrentes')


@staff_member_required(login_url='/admin-panel/login/')
def agregar_excepcion(request, pk):
    rec = get_object_or_404(ReservaRecurrente, pk=pk)
    if request.method == 'POST':
        fecha_str = request.POST.get('fecha', '').strip()
        motivo = request.POST.get('motivo', '').strip()
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Fecha inválida.')
            return redirect('admin_recurrente_editar', pk=pk)
        if fecha.weekday() != rec.dia_semana:
            messages.error(request, 'La fecha no coincide con el día de semana de la recurrente.')
            return redirect('admin_recurrente_editar', pk=pk)
        ReservaRecurrenteExcepcion.objects.get_or_create(
            recurrente=rec, fecha=fecha, defaults={'motivo': motivo}
        )
        messages.success(request, 'Excepción agregada.')
    return redirect('admin_recurrente_editar', pk=pk)


@staff_member_required(login_url='/admin-panel/login/')
def quitar_excepcion(request, pk, exc_pk):
    rec = get_object_or_404(ReservaRecurrente, pk=pk)
    exc = get_object_or_404(ReservaRecurrenteExcepcion, pk=exc_pk, recurrente=rec)
    exc.delete()
    messages.success(request, 'Excepción quitada.')
    return redirect('admin_recurrente_editar', pk=pk)
