from django.shortcuts import render

def calendario(request):
    return render(request, 'reservas/calendario.html')

def formulario(request):
    return render(request, 'reservas/formulario.html')