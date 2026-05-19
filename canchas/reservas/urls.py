from django.urls import path
from .views import client, admin_panel, api, recurrentes, pos, guayos

urlpatterns = [
    # =================== CLIENTE ===================
    path('', client.home, name='home'),
    path('canchas/', client.cancha_lista, name='cancha_lista'),
    path('canchas/<int:pk>/', client.cancha_detalle, name='cancha_detalle'),

    # Flujo de reserva legacy (6 pasos) — la nueva landing reemplaza esto, pero
    # las URLs se mantienen por compat.
    path('reservar/', client.booking_step1, name='booking_step1'),
    path('reservar/fecha/', client.booking_step2, name='booking_step2'),
    path('reservar/duracion/', client.booking_step3, name='booking_step3'),
    path('reservar/horario/', client.booking_step4, name='booking_step4'),
    path('reservar/datos/', client.booking_step5, name='booking_step5'),
    path('reservar/pago/', client.booking_step6, name='booking_step6'),
    path('reservar/confirmar/', client.booking_confirmar, name='booking_confirmar'),

    # Historial
    path('mis-reservas/', client.historial, name='historial'),

    # =================== ADMIN PANEL ===================
    path('admin-panel/login/', admin_panel.admin_login, name='admin_login'),
    path('admin-panel/logout/', admin_panel.admin_logout, name='admin_logout'),
    path('admin-panel/', admin_panel.admin_dashboard, name='admin_dashboard'),

    # Negocio
    path('admin-panel/negocio/', admin_panel.negocio_edit, name='admin_negocio'),

    # Canchas CRUD
    path('admin-panel/canchas/', admin_panel.cancha_admin_lista, name='admin_canchas'),
    path('admin-panel/canchas/crear/', admin_panel.cancha_admin_crear, name='admin_cancha_crear'),
    path('admin-panel/canchas/<int:pk>/editar/', admin_panel.cancha_admin_editar, name='admin_cancha_editar'),
    path('admin-panel/canchas/<int:pk>/eliminar/', admin_panel.cancha_admin_eliminar, name='admin_cancha_eliminar'),

    # Reservas admin
    path('admin-panel/reservas/', admin_panel.reserva_admin_lista, name='admin_reservas'),
    path('admin-panel/reservas/crear/', admin_panel.reserva_admin_crear, name='admin_reserva_crear'),
    path('admin-panel/reservas/<int:pk>/', admin_panel.reserva_admin_detalle, name='admin_reserva_detalle'),
    path('admin-panel/reservas/<int:pk>/eliminar/', admin_panel.reserva_admin_eliminar, name='admin_reserva_eliminar'),
    path('admin-panel/reservas/<int:pk>/pago/<str:nuevo_pago>/', admin_panel.reserva_cambiar_pago, name='admin_reserva_pago'),
    path('admin-panel/reservas/<int:pk>/<str:nuevo_estado>/', admin_panel.reserva_cambiar_estado, name='admin_reserva_estado'),

    # Calendario admin
    path('admin-panel/calendario/', admin_panel.admin_calendario, name='admin_calendario'),

    # Reservas recurrentes
    path('admin-panel/recurrentes/', recurrentes.lista, name='admin_recurrentes'),
    path('admin-panel/recurrentes/crear/', recurrentes.crear, name='admin_recurrente_crear'),
    path('admin-panel/recurrentes/<int:pk>/editar/', recurrentes.editar, name='admin_recurrente_editar'),
    path('admin-panel/recurrentes/<int:pk>/eliminar/', recurrentes.eliminar, name='admin_recurrente_eliminar'),
    path('admin-panel/recurrentes/<int:pk>/estado/<str:nuevo_estado>/', recurrentes.cambiar_estado, name='admin_recurrente_estado'),
    path('admin-panel/recurrentes/<int:pk>/excepcion/', recurrentes.agregar_excepcion, name='admin_recurrente_excepcion'),
    path('admin-panel/recurrentes/<int:pk>/excepcion/<int:exc_pk>/quitar/', recurrentes.quitar_excepcion, name='admin_recurrente_excepcion_quitar'),

    # POS — productos
    path('admin-panel/productos/', pos.producto_lista, name='admin_productos'),
    path('admin-panel/productos/crear/', pos.producto_crear, name='admin_producto_crear'),
    path('admin-panel/productos/<int:pk>/editar/', pos.producto_editar, name='admin_producto_editar'),
    path('admin-panel/productos/<int:pk>/eliminar/', pos.producto_eliminar, name='admin_producto_eliminar'),

    # POS — caja
    path('admin-panel/pos/', pos.pos, name='admin_pos'),
    path('admin-panel/pos/registrar/', pos.pos_registrar, name='admin_pos_registrar'),
    path('admin-panel/ventas/', pos.venta_lista, name='admin_ventas'),
    path('admin-panel/ventas/export/', pos.venta_export_csv, name='admin_ventas_export'),

    # Reportes
    path('admin-panel/reportes/', pos.reportes, name='admin_reportes'),

    # Guayos — inventario
    path('admin-panel/guayos/', guayos.lista, name='admin_guayos'),
    path('admin-panel/guayos/crear/', guayos.crear, name='admin_guayo_crear'),
    path('admin-panel/guayos/<int:pk>/editar/', guayos.editar, name='admin_guayo_editar'),
    path('admin-panel/guayos/<int:pk>/eliminar/', guayos.eliminar, name='admin_guayo_eliminar'),

    # Guayos — alquileres
    path('admin-panel/guayos/alquileres/', guayos.alquileres, name='admin_alquileres_guayos'),
    path('admin-panel/guayos/alquilar/', guayos.alquilar, name='admin_alquilar_guayo'),
    path('admin-panel/guayos/alquileres/<int:pk>/devolver/', guayos.devolver, name='admin_alquiler_guayo_devolver'),
    path('admin-panel/guayos/alquileres/<int:pk>/perdido/', guayos.marcar_perdido, name='admin_alquiler_guayo_perdido'),

    # =================== API ===================
    path('api/reservas/', api.obtener_reservas, name='api_reservas'),
    path('api/reservas/<str:fecha>/', api.reservas_por_dia, name='reservas_por_dia'),
    path('api/disponibilidad/', api.api_disponibilidad, name='api_disponibilidad'),
    path('api/disponibilidad-dia/', api.disponibilidad_dia, name='api_disponibilidad_dia'),
    path('api/booking/create/', api.booking_create, name='api_booking_create'),
]
