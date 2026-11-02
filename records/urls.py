from django.urls import path

from . import views, react_api


urlpatterns = [
    path("equipo/<int:pk>/resolver-estado/", views.resolve_equipment_status, name="resolve_equipment_status"),
    path("carta/<int:pk>/pdf/", views.letter_pdf, name="letter_pdf"),
    path("api/dashboard/", react_api.dashboard_data, name="dashboard_data"),
    path("", views.dashboard, name="dashboard"),
    path("perfil/", views.profile, name="profile"),
    path("cartas/", views.letters, name="letters"),
    path("carta/<int:pk>/editar/", views.edit_letter, name="edit_letter"),
    path("desmovilizacion/<int:pk>/editar/", views.edit_movement, name="edit_movement"),
    path("cargar/", views.upload_letters, name="upload_letters"),
    path("cargar/confirmar/", views.confirm_upload, name="confirm_upload"),
    path("registro/nuevo/", views.manual_record, name="manual_record"),
    path("registro/<int:pk>/editar/", views.edit_presentation, name="edit_presentation"),
    path("carta/<int:pk>/eliminar/", views.delete_letter, name="delete_letter"),
    path("exportar/csv/", views.export_csv, name="export_csv"),
    path("exportar/xlsx/", views.export_xlsx, name="export_xlsx"),
]
