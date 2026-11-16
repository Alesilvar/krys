# Instalación y desarrollo

## Requisitos

En Ubuntu instala o ten disponibles Python 3.12 con soporte para `venv`, Docker Engine con Compose y acceso al servicio Docker, y Poppler (`pdftotext`). Confirma con `python3.12 --version`, `docker compose version`, `docker info` y `pdftotext -v`. Consulta la documentación oficial de cada herramienta para instalarlas. Node.js y npm solo son necesarios para modificar React; utiliza una versión compatible con la versión de Vite fijada en `frontend/package-lock.json`.

Los siguientes comandos se ejecutan desde la raíz del repositorio. Prepara las dependencias Python:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Arranca la base y la aplicación, y en otra terminal crea la primera cuenta:

```bash
./start.sh
```

```bash
.venv/bin/python manage.py createsuperuser
```

Abre <http://127.0.0.1:8000> e inicia sesión. `start.sh` levanta el servicio `db` de Compose, aplica migraciones y ejecuta Django en localhost. `Ctrl+C` termina el servidor web; la base y su volumen permanecen. No utilices las credenciales de desarrollo para un entorno compartido. Para configuración de producción consulta [operación](operacion.md).

## Pruebas

Con PostgreSQL local de Compose disponible:

```bash
.venv/bin/python manage.py test
```

Para ejecutar las pruebas con SQLite sin modificar la base local de desarrollo:

```bash
USE_SQLITE=1 .venv/bin/python manage.py test
```

Django crea una base de pruebas separada. Las pruebas de extracción y algunas pruebas web necesitan muestras PDF no incluidas en Git; por defecto se buscan en el directorio padre del repositorio. Para otra ubicación:

```bash
KRYS_TEST_SAMPLES_DIR=/ruta/a/las/muestras USE_SQLITE=1 .venv/bin/python manage.py test
```

El comando debe terminar sin fallos; si faltan las muestras, revisa el resultado antes de asumir cobertura completa. La suite de extracción independiente también se puede ejecutar con `.venv/bin/python -m pytest test_extractor.py`. Las muestras pueden contener información sensible y no deben incorporarse al repositorio sin autorización.

## Frontend

Para regenerar el archivo versionado `static/react/app.js` tras cambiar React:

```bash
cd frontend
npm ci
npm run build
```

El arranque normal usa el archivo compilado y no requiere Node. Django sigue gestionando sesiones, formularios y reglas; sin JavaScript se usan las plantillas HTML existentes, con navegación adaptable también en pantallas pequeñas. Para comprobar enlaces de documentación, desde la raíz ejecuta `python3 scripts/check_doc_links.py`.
