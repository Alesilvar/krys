# Operación, seguridad y recuperación

## Alcance y publicación

`docker-compose.yml` solo configura PostgreSQL para desarrollo local, con puerto publicado en `127.0.0.1:5433` y credenciales de desarrollo. No constituye un despliegue de producción. El repositorio no define proveedor, infraestructura, servicio web, supervisión ni procedimiento de publicación definitivo: deben acordarse y documentarse para el entorno elegido.

Antes de publicar, define `DJANGO_DEBUG=0`, una `DJANGO_SECRET_KEY` aleatoria de al menos 50 caracteres y `DJANGO_ALLOWED_HOSTS`. Configura HTTPS; Django activa cookies seguras y redirección HTTPS con depuración desactivada. Solo habilita `DJANGO_TRUST_PROXY_HTTPS=1` si un proxy de confianza termina HTTPS y elimina las cabeceras de clientes. Activa `DJANGO_HSTS_SECONDS` después de verificar HTTPS en todo el dominio. Ejecuta `.venv/bin/python manage.py check --deploy` con la configuración real y atiende sus advertencias. Protege credenciales, almacenamiento y acceso administrativo; no sirvas `media/` directamente. La [referencia](referencia-tecnica.md) describe las variables.

## Crear una copia coherente del entorno local

Una copia necesita tanto PostgreSQL como `media/` del mismo momento. Para evitar escrituras intermedias, detén el servidor web y cualquier otro proceso que escriba en la base o en `media/` durante **ambas** copias; mantén PostgreSQL activo. Los comandos siguientes son para la configuración local predeterminada de Compose y se ejecutan en la raíz del repositorio. Usa una carpeta nueva y privada fuera del repositorio, en un sistema con espacio suficiente:

```bash
umask 077
mkdir /ruta/privada/copia-ks
# Mantén detenidos todos los procesos que escriben datos o archivos.
docker compose exec -T db pg_dump -U krys -d krys -Fc > /ruta/privada/copia-ks/base.dump
tar -czf /ruta/privada/copia-ks/media.tar.gz media
```

Si `media/` todavía no existe, registra que la instalación no tiene archivos y conserva esa información junto a la copia. Verifica los códigos de salida de ambos comandos antes de reanudar las escrituras. Protege la copia y guárdala fuera de la máquina. No incluyas `.env` o secretos en el mismo respaldo sin un procedimiento protegido. Para producción, adapta la copia a las credenciales, almacenamiento y herramientas del proveedor; los comandos locales no cubren una base o almacenamiento remoto.

## Ensayar la restauración aislada

Nunca ensayes sobre la base o el directorio `media/` de trabajo. El siguiente ejemplo usa una copia **de confianza** creada con los comandos anteriores y un contenedor PostgreSQL 18 temporal sin red ni volumen persistente; necesita Docker operativo y la imagen disponible. Sustituye las rutas y usa un nombre de contenedor libre. La contraseña es solo para esta prueba aislada:

```bash
mkdir /ruta/privada/ensayo-ks
# La carpeta de ensayo debe estar vacía.
docker run -d --name ks-restauracion-ensayo --network none -e POSTGRES_PASSWORD=ensayo postgres:18-alpine
docker exec ks-restauracion-ensayo pg_isready -U postgres
# Si aún no está listo, repite pg_isready antes de continuar.
docker exec -i ks-restauracion-ensayo pg_restore -U postgres -d postgres --no-owner --no-privileges < /ruta/privada/copia-ks/base.dump
tar -xzf /ruta/privada/copia-ks/media.tar.gz -C /ruta/privada/ensayo-ks
docker exec ks-restauracion-ensayo psql -U postgres -d postgres -c 'SELECT COUNT(*) FROM records_letter;'
```

Comprueba que `pg_restore` termine sin errores, que el conteo sea razonable y que los PDF esperados estén en la carpeta restaurada. Para una validación completa, configura una instancia aislada de KS con esa base y esos archivos, comprueba inicio de sesión, registros y apertura de PDF, y compara con el origen. Este último paso depende de la infraestructura disponible y no está automatizado aquí. Al terminar, detén y elimina el contenedor de ensayo y gestiona las copias temporales conforme a la política de datos aplicable. No restaures archivos de fuentes no confiables.

## Problemas frecuentes

- **No conecta Docker:** comprueba que el servicio esté activo y que tu usuario tenga acceso; no hace falta compartir contraseñas.
- **Falta `.venv` o una dependencia:** sigue la [instalación](instalacion-desarrollo.md) y comprueba la versión de Python.
- **Error al extraer PDF:** confirma que `pdftotext` esté disponible, que el archivo tenga texto seleccionable y sea un PDF válido de hasta 10 MB; revisa la cadena documental.
- **Error de conexión a la base:** comprueba el estado de Compose, puerto y variables de conexión. Cambiar variables de Django no cambia por sí solo las credenciales de una base existente.
- **Fallan pruebas con archivos ausentes:** revisa `KRYS_TEST_SAMPLES_DIR` y la estructura de muestras descrita en la [guía de desarrollo](instalacion-desarrollo.md).
