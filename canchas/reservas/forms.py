from django import forms
from .models import Negocio, Cancha, Reserva, ReservaRecurrente, Producto


class NegocioForm(forms.ModelForm):
    class Meta:
        model = Negocio
        fields = ['nombre', 'descripcion', 'telefono', 'email', 'direccion',
                  'logo', 'horario_apertura', 'horario_cierre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-input'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'telefono': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'direccion': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'horario_apertura': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'horario_cierre': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
        }


class CanchaForm(forms.ModelForm):
    class Meta:
        model = Cancha
        fields = ['nombre', 'tipo', 'superficie', 'capacidad', 'precio_por_hora',
                  'imagen', 'caracteristicas', 'reglas', 'horario_apertura',
                  'horario_cierre', 'es_techada', 'is_active']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-input'}),
            'tipo': forms.Select(attrs={'class': 'form-input'}),
            'superficie': forms.Select(attrs={'class': 'form-input'}),
            'capacidad': forms.NumberInput(attrs={'class': 'form-input'}),
            'precio_por_hora': forms.NumberInput(attrs={'class': 'form-input', 'step': '100'}),
            'caracteristicas': forms.Textarea(attrs={'class': 'form-input', 'rows': 3,
                                                     'placeholder': 'Una característica por línea'}),
            'reglas': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'horario_apertura': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'horario_cierre': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
        }


class ReservaAdminForm(forms.ModelForm):
    class Meta:
        model = Reserva
        fields = ['cancha', 'fecha_inicio', 'fecha_fin', 'duracion',
                  'cliente_nombre', 'cliente_telefono', 'tipo_pago',
                  'estado_pago', 'nota']
        widgets = {
            'cancha': forms.Select(attrs={'class': 'form-input'}),
            'fecha_inicio': forms.DateTimeInput(attrs={'class': 'form-input', 'type': 'datetime-local'}),
            'fecha_fin': forms.DateTimeInput(attrs={'class': 'form-input', 'type': 'datetime-local'}),
            'duracion': forms.Select(attrs={'class': 'form-input'}),
            'cliente_nombre': forms.TextInput(attrs={'class': 'form-input'}),
            'cliente_telefono': forms.TextInput(attrs={'class': 'form-input'}),
            'tipo_pago': forms.Select(attrs={'class': 'form-input'}),
            'estado_pago': forms.Select(attrs={'class': 'form-input'}),
            'nota': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
        }


def _hora_choices():
    """Etiquetas legibles para horas 5-29. Las horas >=24 son madrugada del día siguiente."""
    out = []
    for h in range(5, 30):
        display = h % 24
        suffix = ' (madrugada)' if h >= 24 else ''
        out.append((h, f"{display:02d}:00{suffix}"))
    return out


class ReservaRecurrenteForm(forms.ModelForm):
    hora_inicio = forms.TypedChoiceField(
        choices=_hora_choices, coerce=int,
        label='Hora de inicio',
        widget=forms.Select(attrs={'class': 'form-input'}),
        help_text='Si la cancha cierra después de medianoche, las horas con "(madrugada)" son del día siguiente.',
    )

    class Meta:
        model = ReservaRecurrente
        fields = ['cancha', 'dia_semana', 'hora_inicio', 'duracion',
                  'fecha_desde', 'fecha_hasta',
                  'cliente_nombre', 'cliente_telefono', 'cliente_email',
                  'precio_acordado', 'estado', 'nota']
        widgets = {
            'cancha': forms.Select(attrs={'class': 'form-input'}),
            'dia_semana': forms.Select(attrs={'class': 'form-input'}),
            'duracion': forms.Select(attrs={'class': 'form-input'}),
            'fecha_desde': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'fecha_hasta': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'cliente_nombre': forms.TextInput(attrs={'class': 'form-input'}),
            'cliente_telefono': forms.TextInput(attrs={'class': 'form-input'}),
            'cliente_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'precio_acordado': forms.NumberInput(attrs={'class': 'form-input', 'step': '100'}),
            'estado': forms.Select(attrs={'class': 'form-input'}),
            'nota': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
        }

    def clean(self):
        cleaned = super().clean()
        fd = cleaned.get('fecha_desde')
        fh = cleaned.get('fecha_hasta')
        if fd and fh and fh < fd:
            raise forms.ValidationError("La fecha 'hasta' debe ser posterior a la fecha 'desde'.")
        return cleaned


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'categoria', 'precio', 'stock', 'imagen', 'is_active']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-input'}),
            'categoria': forms.Select(attrs={'class': 'form-input'}),
            'precio': forms.NumberInput(attrs={'class': 'form-input', 'step': '100'}),
            'stock': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Vacío = sin control'}),
            'imagen': forms.ClearableFileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
        }
