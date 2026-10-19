# Krys · control documental SST

Primera versión web para registrar cartas CPC, respuestas AAM y una fila por
equipo. Extrae datos de PDF con texto seleccionable, permite revisarlos antes
de guardar y mantiene los archivos como respaldo.

## Funciones incluidas

- Inicio de sesión y trazabilidad del usuario que crea o modifica datos.
- Carga conjunta o separada de cartas CPC y AAM.
- Vista previa antes de guardar y fecha de recepción ingresada por el usuario.
- Relación estricta de una respuesta AAM por carta CPC.
- Cálculo del tipo de trámite siguiendo la cadena documental.
- Advertencias para equipos de una respuesta que no aparecen en la carta CPC.
- Ingreso manual con PDF CPC/AAM opcional como respaldo.
- Edición de filas y cartas, y eliminación permanente de la carta completa.
- Búsqueda, filtros y exportación a CSV o Excel.

## Tecnología

- Python 3.12 y Django 5.2.
- PostgreSQL 18 en Docker.
- `pdftotext` de Poppler para leer los PDF sin OCR.
- HTML y CSS adaptables a escritorio y móvil.
- openpyxl para exportar Excel.

## Arranque local

Desde esta carpeta:

```bash
./start.sh
```

Después abre <http://127.0.0.1:8000>. El script inicia PostgreSQL, aplica las
migraciones y levanta la web. Se detiene con `Ctrl+C`; la base permanece en el
volumen de Docker.

Para crear otra cuenta con acceso completo a la aplicación:

```bash
.venv/bin/python manage.py createsuperuser
```

## Pruebas

```bash
.venv/bin/python manage.py test
```

Las 22 pruebas actuales cubren los seis PDF aportados (150/118, 178/127 y
190/136), la segunda presentación, el modelo de datos, el ingreso manual, la
exportación y el borrado completo.

## Configuración

Las variables opcionales son `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`,
`DJANGO_ALLOWED_HOSTS`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_HOST` y `POSTGRES_PORT`. Los valores predeterminados son solo para
desarrollo local. Para publicar la aplicación se deben definir secretos y
almacenamiento persistente del proveedor elegido.
