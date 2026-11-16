# KS · control documental SST

KS registra cartas CPC y respuestas AAM, extrae información de PDF con texto seleccionable y permite consultar el historial de equipos, sus evaluaciones y desmovilizaciones. Incluye revisión previa a la importación, control de acceso, búsqueda y exportación a CSV y Excel.

## Comenzar

Se necesitan Python 3.12, Docker con Compose y acceso a su servicio, Poppler y Tesseract con datos de español para PDF escaneados. Desde esta carpeta, después de preparar los requisitos y el entorno como se explica en [instalación y desarrollo](docs/instalacion-desarrollo.md):

```bash
./start.sh
```

Abre <http://127.0.0.1:8000>. El script inicia PostgreSQL, aplica las migraciones y ejecuta el servidor local; detén el servidor con `Ctrl+C`. Crea la primera cuenta con `.venv/bin/python manage.py createsuperuser`.

## Documentación

- [Instalación y desarrollo](docs/instalacion-desarrollo.md): preparación desde cero, pruebas y frontend.
- [Guía de usuario](docs/guia-usuario.md): carga, consulta, edición y permisos.
- [Referencia técnica](docs/referencia-tecnica.md): arquitectura, reglas, configuración y API interna.
- [Operación](docs/operacion.md): producción, seguridad, copias y recuperación.
- [Contribución y mantenimiento](CONTRIBUTING.md): revisión y actualización de la documentación en cada cambio.

El proyecto usa Django, PostgreSQL y una interfaz React con alternativas HTML. El archivo React compilado está incluido en el repositorio. Las muestras PDF utilizadas por algunas pruebas no están versionadas. Las condiciones de licencia, el responsable y el canal de soporte aún no están definidos en este repositorio.
