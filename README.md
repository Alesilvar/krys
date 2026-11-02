# KS · control documental SST

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
- Desmovilización con historial separado: un equipo conserva su evaluación SST
  y puede cambiar posteriormente de Activo a Retirado.
- Extracción de marca, modelo, serie, año y fecha de salida en solicitudes de
  retiro, junto con la carta AAM que autoriza el movimiento.
- Ingreso manual con PDF CPC/AAM opcional como respaldo.
- Edición de filas y cartas, y eliminación permanente de la carta completa.
- Búsqueda, filtros y exportación a CSV o Excel.

## Tecnología

- Python 3.12 y Django 5.2.
- PostgreSQL 18 en Docker.
- `pdftotext` de Poppler para leer los PDF sin OCR.
- Extracción tolerante a listas, viñetas, placas en prosa y respuestas de
  conformidad que no vuelven a enumerar los equipos.
- HTML y CSS adaptables a escritorio y móvil.
- openpyxl para exportar Excel.

## Arquitectura

KS es un monolito modular: se ejecuta y despliega como una sola aplicación,
pero el módulo `records` separa sus responsabilidades para evitar que las
reglas de negocio dependan de las páginas web.

- `models.py`: entidades y relaciones persistentes.
- `forms.py`: validación de entradas web.
- `selectors.py`: consultas y métricas de lectura.
- `use_cases.py`: altas, modificaciones y eliminación transaccional.
- `services.py`: importación y persistencia de lotes PDF.
- `exports.py`: transformación a CSV y Excel.
- `views.py`: capa HTTP; coordina formularios, casos de uso y respuestas.
- `extractor.py`: motor independiente de extracción documental.

Esta organización permite reutilizar los mismos casos de uso desde comandos o
una API futura sin separar todavía el frontend y el backend ni duplicar reglas.

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

Las 42 pruebas actuales cubren los PDF aportados, formatos variables de listas
y observaciones, aprobaciones generales, cadenas de subsanación, el modelo de
datos, la desmovilización, el inventario actual por tipo, la tabla histórica
unificada, el ingreso manual, la importación web, la exportación y el borrado
completo.

## Configuración

Las variables opcionales son `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`,
`DJANGO_ALLOWED_HOSTS`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_HOST` y `POSTGRES_PORT`. Los valores predeterminados son solo para
desarrollo local. Para publicar la aplicación se deben definir secretos y
almacenamiento persistente del proveedor elegido.

## Frontend React

La interfaz usa React Router para navegar entre páginas sin recargarlas y
componentes compartidos para navegación, formularios,
botones y paneles. Django entrega los datos y procesa los formularios, las sesiones
y las reglas de negocio; el panel consulta `/api/dashboard/`. Las plantillas
existentes quedan como alternativa si JavaScript no está disponible.
El archivo compilado está incluido para que el arranque habitual no requiera Node.
Para modificar y volver a compilar la interfaz, instala Node.js compatible con Vite,
luego ejecuta:

```bash
cd frontend
npm ci
npm run build
```

Las páginas existentes se muestran si JavaScript está desactivado. La autenticación y las reglas de negocio siguen en Django.

## Permisos de la aplicación

Todas las cuentas creadas antes de aplicar la migración de permisos conservan
acceso completo a los registros. Las cuentas nuevas pueden consultar y exportar;
para permitirles modificar datos, un superusuario puede asignarlas desde `/admin/`
al grupo **Edición**. El grupo **Administración de registros** también permite
eliminar cartas; **Consulta** es opcional para identificar a quienes solo leen.
Los permisos se comprueban en el servidor. Las cuentas de superusuario conservan
todos los permisos. Los PDF se sirven mediante una ruta autenticada.

## Publicación y respaldos

En producción define `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY` (al menos 50
caracteres aleatorios) y `DJANGO_ALLOWED_HOSTS`. Configura HTTPS antes de
publicar: las cookies y la redirección segura se activan en ese modo. Si un
proxy de confianza termina HTTPS y elimina las cabeceras enviadas por clientes,
configura `DJANGO_TRUST_PROXY_HTTPS=1`. Activa `DJANGO_HSTS_SECONDS` solo
después de verificar HTTPS para todo el dominio. Ejecuta `manage.py check
--deploy` con la configuración real y resuelve sus advertencias.

Un respaldo debe incluir una copia coherente de PostgreSQL y del directorio
`media/` del mismo momento. Conserva copias fuera de la máquina y ensaya la
restauración en un entorno aislado antes de depender de ellas. No expongas
`media/` mediante el servidor web: los PDF se entregan por la aplicación.
