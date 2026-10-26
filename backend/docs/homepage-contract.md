# Contratos de la portada — 26/10/2026

## Capas

- `api/auth.py`: declara HTTP y dependencias; delega el logout en `AuthService`.
- `services/auth_service.py`: define la revocación de todas las sesiones.
- `repositories/user_repository.py`: incrementa atómicamente `User.session_version`. La transacción se confirma mediante `get_db`, igual que el resto de operaciones.
- `api/health_documents.py`: declara parámetros, esquema de respuesta y traducción de errores HTTP.
- `services/health_document_service.py`: selecciona el alcance por rol, valida la consulta y construye los resultados públicos.
- `repositories/health_document_repository.py`: realiza filtros, joins, ordenación, conteo y paginación SQL. Los permisos se aplican antes de contar o paginar.
- `schemas/health_documents.py`: expone únicamente los metadatos del contrato de búsqueda.

No se modifican modelos, tablas, migraciones, CORS ni servicios profesionales.

## POST /auth/logout

Autenticación: `Authorization: Bearer <access_token>`. Sin cuerpo. Respuesta: `204 No Content`; tokens ausentes, vencidos o revocados producen `401`.

Revoca **todas** las sesiones previas de la cuenta mediante la versión global ya existente. Afecta a access y refresh tokens; no es un logout individual por dispositivo. Permite un nuevo inicio de sesión. Los JWT no se almacenan ni se registran en logs.

Los WebSockets de chat existentes vuelven a validar el token al recibir un evento, incluido `ping`, y cierran con `4401` si ya no es válido. No se garantiza cierre inmediato de un socket inactivo. Los JWT de Jitsi emitidos previamente son un contrato independiente y conservan su vencimiento.

## GET /health/documents/search

Autenticación Bearer. Roles: `patient` o `professional`; `admin` recibe `403` porque el acceso administrativo no implica acceso clínico global.

Parámetros:

| Nombre | Contrato |
| --- | --- |
| `q` | Obligatorio, 1–100 caracteres después de recortar espacios |
| `tipo` | Opcional: `informe`, `analitica`, `otro` |
| `page` | Entero >= 1, predeterminado 1 |
| `page_size` | Entero entre 1 y 100, predeterminado 20 |

Búsqueda parcial sin distinguir mayúsculas/minúsculas en `descripcion` y `tipo`. `%`, `_` y `\` se interpretan como texto literal. No se busca dentro de PDFs/imágenes, en rutas de almacenamiento ni en nombres originales, que el modelo actual no conserva.

Respuesta: `{ documents, total, page, page_size }`. Cada elemento contiene `id`, `patient_user_id`, `tipo`, `descripcion` nullable y `fecha_subida` ISO datetime. No devuelve `file_url`. Orden: fecha de subida descendente e ID descendente como desempate. Sin coincidencias: lista vacía y total 0. Consulta inválida: `422`.

Los pacientes solo ven documentos de su propio perfil. Los profesionales solo ven documentos de perfiles con `share_health_data=true` y una cita compartida, siguiendo la misma regla que las descargas existentes. `patient_user_id` es el ID de la cuenta, adecuado para el endpoint existente de descarga profesional.

Las descargas siguen pasando por las comprobaciones actuales de `HealthDocumentService`; encontrar un resultado no sustituye la autorización en el momento de descargarlo. Los consentimientos pueden cambiar entre ambas solicitudes.

## Pruebas

`backend/venv/Scripts/python.exe -m unittest discover -s backend/tests` desde la raíz requiere configurar la importación de `app`; la forma habitual es ejecutar `./venv/Scripts/python.exe -m unittest discover -s tests` desde `backend/`.

Los nuevos tests usan SQLite en memoria o repositorios falsos, con datos sintéticos exclusivamente en `tests/`. Los tests HTTP no inician el lifespan ni el despachador de notificaciones y no consultan datos reales. Las pruebas de consulta con SQLite verifican aislamiento, comodines y paginación; no equivalen a una prueba con PostgreSQL de producción.
