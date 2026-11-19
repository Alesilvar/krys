# Inventario inicial de formatos de cartas

Auditoría de la carpeta local `../PDF-PSR2`, realizada el 19 de noviembre de 2026 con `scripts/audit_pdfs.py`. El informe completo es local y puede contener información de los documentos; no se incluye en el repositorio.

```bash
.venv/bin/python scripts/audit_pdfs.py ../PDF-PSR2 --output /tmp/krys-auditoria.json
```

## Resultado automático

| Resultado del análisis | PDF |
| --- | ---: |
| Presentaciones procesadas | 27 |
| Respuestas procesadas | 19 |
| Desmovilizaciones procesadas | 2 |
| Archivos duplicados | 5 |
| Errores o documentos que requieren revisión | 82 |
| **Total** | **135** |

El proceso produjo 112 filas y 7 advertencias de vinculación. «Procesado» significa que el analizador devolvió un resultado, no que este haya sido revisado ni que todos los datos sean correctos. Las cifras no son porcentajes de precisión. La carpeta también contiene documentos ajenos al registro de equipos: un error no significa necesariamente que el PDF sea una carta de equipos válida. El informe detallado permite revisar cada caso.

Los 82 errores se distribuyen así: 37 sin evaluaciones reconocidas; 35 sin equipos reconocidos; 3 sin conformidad de retiro reconocida; 3 sin tabla de desmovilización compatible; 2 sin referencia CPC reconocida; y 2 sin número de carta reconocido. Estas categorías reflejan el primer error detectado, no una clasificación definitiva del contenido.

## Ejemplos revisados y siguientes prioridades

| Ejemplo | Formato observado | Resultado esperado o situación |
| --- | --- | --- |
| CPC 0682 y AAM 0724 | Lista numerada con cuatro placas y una serie; respuesta con aprobación de la lista | Cinco equipos aprobados; prueba automatizada con los dos PDF. La autorización está sujeta a verificación física. |
| AAM 0204 | Observaciones en párrafos encabezados por placa entre paréntesis, repartidos en dos páginas | Nueve placas observadas. La carta menciona diez unidades, pero solo detalla nueve. Además, indica F3K-736 y la CPC 0261 indica F3Q-736; VDK-020 tampoco tiene evaluación identificada. No se atribuyen resultados por suposición. Prueba automatizada con el PDF. |
| AAM 0223, referencia CPC 0256 | Observaciones individuales en viñetas, con variaciones de puntuación | Prioridad pendiente: revisar las ocho observaciones y sus textos antes de preparar resultados esperados. |
| AAM 0273 | Aprobación conjunta con placa e identificación de excavadora | Prioridad pendiente: comprobar cómo vincular el identificador compuesto con el de la carta CPC, sin equipararlos por suposición. |
| CPC 0603 | Subsanación y sustitución de una carta, con dos números de serie y equipo ya desmovilizado | Prioridad pendiente: preservar la distinción entre el equipo correcto, el número equivocado y la sustitución; no asumir una nueva autorización. |
| CPC 0223 | Correspondencia sobre revisión de documentos de diseño | Ejemplo ajeno al registro de equipos; no debe contarse como formato de equipo faltante sin clasificación humana. |

Las pruebas de regresión existentes también cubren otros ejemplos de presentación, observaciones, aprobaciones, subsanaciones y desmovilización. Se ejecutan con `.venv/bin/python -m unittest test_extractor`. Los PDF de ejemplo son locales y las pruebas que los requieren se omiten si faltan.

Para ampliar la cobertura, revisar cada documento y anotar los identificadores, la referencia, el resultado y el detalle esperados antes de modificar el extractor. Mantener los casos ambiguos sin resultado automático. Repetir la auditoría tras cada cambio y comparar tanto los errores como las advertencias y los resultados revisados; una reducción de errores por sí sola no demuestra exactitud.
