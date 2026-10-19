from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("cargar/", views.upload_letters, name="upload_letters"),
    path("cargar/confirmar/", views.confirm_upload, name="confirm_upload"),
    path("registro/nuevo/", views.manual_record, name="manual_record"),
    path("registro/<int:pk>/editar/", views.edit_presentation, name="edit_presentation"),
    path("carta/<int:pk>/eliminar/", views.delete_letter, name="delete_letter"),
    path("exportar/csv/", views.export_csv, name="export_csv"),
    path("exportar/xlsx/", views.export_xlsx, name="export_xlsx"),
]
