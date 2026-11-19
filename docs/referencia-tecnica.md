# Referencia técnica

## Arquitectura y flujo

KS es un monolito Django. React Router proporciona navegación y componentes; Django entrega páginas y datos, gestiona sesiones y formularios, valida permisos y conserva las reglas. Las páginas de inicio y registros consultan la API interna; el historial de búsqueda se encuentra en `/registros/`. Los enlaces antiguos a la raíz con filtros redirigen a esa página. Las plantillas Django son una alternativa cuando JavaScript está desactivado.

La carga envía archivos a `records.services`, que valida los PDF, usa `extractor.py` y Poppler para extraer texto; si el PDF completo no contiene texto seleccionable, convierte sus páginas a imágenes y usa Tesseract en español como alternativa OCR. Después reúne las cadenas documentales y prepara una vista previa. Al confirmar, persiste cartas, equipos, evaluaciones y movimientos; `records.use_cases` concentra operaciones manuales transaccionales, `records.selectors` las consultas y métricas y `records.exports` las exportaciones. `records.models` define las entidades; `records.forms` y `records.views` validan y coordinan solicitudes HTTP. Los PDF se guardan bajo `media/` y se sirven mediante una ruta autenticada.

## Modelo y reglas principales

- `Letter` identifica una carta por número completo y por dirección y correlativo; una respuesta AAM se vincula a una única carta CPC. Una CPC posterior puede referenciar una respuesta anterior para representar una subsanación.
- `Equipment` identifica el equipo por código; `Presentation` registra su presentación por carta y `Evaluation` su resultado SST. `EquipmentMovement` registra solicitudes y autorizaciones de desmovilización por separado. `AuditEvent` conserva eventos de auditoría.
- Si se detectan varias respuestas de ingreso para una carta CPC durante la extracción, ninguna se asigna automáticamente a sus filas y se emite una advertencia. Esto evita elegir una por orden de carga; el modelo de persistencia actual todavía admite una sola respuesta por CPC.
- Los tipos reconocidos y sus equivalencias se normalizan al registrar equipos. El inventario agrupa también equivalencias históricas sin modificar los registros originales. Los tipos desconocidos o ambiguos se conservan como texto: el catálogo todavía no es obligatorio y, por ejemplo, una cisterna de agua no se considera potable sin evidencia.
- La extracción requiere PDF con texto seleccionable; las vistas previas pueden incluir advertencias y conflictos de evaluación. Un conflicto solo reemplaza una evaluación existente tras la confirmación explícita del usuario.
- El estado operativo se deriva de las fechas de aprobación AAM, solicitud de retiro CPC y autorización de retiro AAM. Una aprobación posterior puede reactivar el equipo. Si una aprobación y un retiro comparten la fecha más reciente, queda **Por revisar** hasta que un editor resuelva el empate; la decisión se invalida al cambiar los eventos o sus fechas.
- El gráfico de equipos activos agrupa por tipo los equipos con estado activo y al menos una presentación o movimiento, incluidos los que no tienen tipo; excluye equipos sin historial y los demás estados. No depende de los filtros del historial.
- El inventario por tipo cuenta equipos con alguna evaluación aprobada y estado activo o retiro solicitado, con tipo no vacío; excluye retirados y equipos por revisar. El historial y sus filtros combinan presentaciones y desmovilizaciones; al filtrar por resultado SST se excluyen movimientos.

## Variables de entorno

Los valores mostrados son predeterminados locales, no credenciales de producción. Las variables PostgreSQL de Django no modifican automáticamente las credenciales fijas del servicio Compose: cualquier cambio de credenciales requiere coordinar la configuración y el estado de la base.

| Variable | Predeterminado | Uso |
|---|---|---|
| `DJANGO_SECRET_KEY` | Clave insegura local en `config/settings.py` | En producción debe ser distinta de la local y tener al menos 50 caracteres. |
| `DJANGO_DEBUG` | `1` | Solo `1` activa depuración; usa `0` en producción. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Lista separada por comas; debe definirse explícitamente en producción. |
| `DJANGO_TRUST_PROXY_HTTPS` | Desactivado | `1` confía en `X-Forwarded-Proto` cuando la depuración está desactivada; requiere un proxy de confianza. |
| `DJANGO_HSTS_SECONDS` | `0` | Duración HSTS en segundos con depuración desactivada. |
| `USE_SQLITE` | Desactivado | `1` usa `db.sqlite3` en vez de PostgreSQL; Django utiliza una base de pruebas separada al ejecutar tests. |
| `POSTGRES_DB` / `POSTGRES_USER` | `krys` / `krys` | Base y usuario de la conexión Django. |
| `POSTGRES_PASSWORD` | `krys_dev_password` | Contraseña de desarrollo de Django y Compose. |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `127.0.0.1` / `5433` | Servidor y puerto de PostgreSQL para Django ejecutado en el host. |
| `KRYS_TEST_SAMPLES_DIR` | Directorio padre del repositorio | Raíz donde las pruebas buscan las muestras PDF, incluida la subcarpeta `ejemplo-cuarta`. |

## API interna del panel

`GET /api/dashboard/` requiere una sesión autenticada; una solicitud sin sesión sigue la redirección de inicio de sesión de Django. Acepta parámetros opcionales `q`, `result` (`APPROVED` o `OBSERVED`) y `status` (`ACTIVE`, `REQUESTED`, `RETIRED` o `REVIEW`). Devuelve JSON con `canEdit`, `metrics`, `records` y `filters`. `metrics` contiene los contadores generales, inventario por tipo y hasta cinco cartas CPC sin respuesta, ordenadas por fecha de carta y luego por identificador; `records` incluye identificadores, datos de carta y equipo, estado, resultado, enlaces PDF y acciones disponibles. Las URL de edición y resolución pueden ser `null` según permisos; la eliminación se ofrece desde el expediente de la carta. Los enlaces PDF también pueden ser `null`. Las fechas visibles se presentan como `dd/mm/aaaa`, con `—` o cadena vacía cuando corresponda. Es una interfaz interna de la aplicación, sin compromiso de compatibilidad pública independiente.

## Pruebas y cambios

La [guía de desarrollo](instalacion-desarrollo.md) explica comandos y ubicación de muestras. Las pruebas cubren, entre otros, extracción, importación, reglas, permisos, API y exportación. Consulta [contribución](../CONTRIBUTING.md) para mantener esta referencia junto con los cambios de código.

### Ejemplos y auditoría de formatos

El [inventario inicial de formatos](inventario-formatos-cartas.md) reúne ejemplos revisados, límites de cobertura y el comando para repetir la auditoría local de PDF. Los resultados automáticos deben contrastarse con las cartas originales.
