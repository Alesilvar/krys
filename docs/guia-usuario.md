# Guía de usuario

KS mantiene cartas CPC, respuestas AAM y registros de equipos. Inicia sesión con una cuenta proporcionada por el administrador; la pantalla principal muestra el historial y los indicadores.

## Consultar y exportar

En **Registros**, el gráfico de pastel distribuye por tipo los equipos con estado activo; excluye los que tienen retiro solicitado, están retirados o están por revisar. Incluye los equipos sin tipo en una categoría separada. En la misma pantalla, busca por placa, carta o tipo; también puedes filtrar por resultado SST y estado operativo. Pulsa **Filtrar** y usa **CSV** o **Excel** para exportar la selección. Los indicadores resumen el conjunto de datos, no solo la selección. En **Cartas**, busca por número o equipo y filtra por respuesta pendiente o respondida; abre un expediente para ver cartas, equipos y PDF disponibles.

## Cargar cartas PDF

1. Con permiso de edición, abre **Cargar cartas**, selecciona una o varias cartas CPC y AAM y pulsa **Extraer y revisar**. Incluye documentos anteriores cuando sean necesarios para establecer la cadena. Los PDF deben tener texto seleccionable; KS no hace reconocimiento óptico (OCR). Cada archivo debe ser un PDF válido de hasta 10 MB.
2. Compara los datos extraídos y las advertencias con los documentos originales. Introduce la fecha de recepción de cada CPC y, si corresponde, el dato adicional de cada equipo.
3. Si se indica un conflicto con una evaluación existente, revisa ambos valores y marca la casilla de reemplazo solo si deseas sustituirla. Si no la marcas, la evaluación actual se conserva.
4. Pulsa **Guardar datos**. La vista previa no guarda registros hasta su confirmación. Si caduca o aparece un error, vuelve a cargar y revisar los archivos.

Si hay un dato extraído incorrectamente, no lo des por válido: revisa los documentos y, tras guardar, usa las opciones de edición correspondientes. Una respuesta de desmovilización necesita su solicitud referenciada disponible en la carga o en los archivos ya registrados.

## Ingreso y edición manual

En **Ingreso manual**, completa los datos CPC, la fecha de recepción y el equipo. Para una subsanación indica la respuesta AAM anterior; si hay resultado SST, proporciona también el número y la fecha de la respuesta. Adjuntar PDF es opcional. Guarda el registro; si la carta ya existe, se agrega otra fila a esa carta.

En **Registros**, usa **Editar** para una presentación. En **Cartas** puedes editar la carta o el equipo de una desmovilización. Los cambios en datos compartidos de una carta afectan a todos sus equipos. Las validaciones se muestran en el formulario; corrige los campos y vuelve a guardar.

## Estado y empates

El resultado SST y el estado operativo son datos distintos. El equipo puede estar activo, con retiro solicitado, retirado o **Por revisar**. Cuando una aprobación y un retiro empatan en la fecha más reciente, se excluye del inventario en uso. Una persona con permiso de edición puede pulsar **Revisar empate**, comparar los eventos y elegir cuál ocurrió después; la decisión queda auditada y se invalida si cambian los eventos o sus fechas. Las reglas se describen en la [referencia técnica](referencia-tecnica.md).

## Permisos y eliminación

Las cuentas nuevas pueden consultar y exportar. Un superusuario asigna desde `/admin/` el grupo **Edición** para crear y modificar, o **Administración de registros** para modificar y eliminar; **Consulta** identifica opcionalmente a quienes solo leen. Los superusuarios tienen todos los permisos. Las cuentas existentes antes de la migración de permisos conservan acceso completo. Los PDF requieren autenticación.

**Eliminar carta** requiere permiso de administración de registros y solicita confirmación. Borra definitivamente la carta CPC, sus presentaciones y movimientos, la respuesta vinculada y sus PDF disponibles. Las subsanaciones posteriores se conservan, pero dejan de estar vinculadas a esa respuesta. Consulta con el administrador antes de confirmar si necesitas recuperar información.
