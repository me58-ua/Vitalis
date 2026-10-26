# Seguimiento del frontend de Vitalis

Actualizar este archivo después de implementar cada página. Marcar como completado solo lo implementado y verificado; separar dependencias del backend, alcance futuro y pruebas pendientes.

## homePage — 25/10/2026

Referencia: Figma `Isvtz5T0fmCfftwPGfqZiM`, frame `15:166`.

### Implementación

- [x] Inspeccionar routers, autenticación, esquemas y OpenAPI del backend antes de implementar.
- [x] Usar la carpeta existente `frontend/` y conservar `assets/vitalis logo.png`.
- [x] Crear una aplicación React con TypeScript, Vite, React Router, Axios y CSS estándar.
- [x] Implementar portada, tarjetas de servicios y sección de privacidad adaptables a móvil.
- [x] Descargar los recursos gráficos de Figma; usar archivos locales, sin URLs temporales en ejecución.
- [x] Sustituir precisión inventada, estado de análisis ficticio y afirmaciones médicas o de seguridad no respaldadas.
- [x] Usar el título y la descripción de privacidad solicitados.
- [x] Añadir diálogos de acceso y registro de pacientes/profesionales con los campos del contrato real.
- [x] Mostrar el nombre y el rol obtenidos mediante `GET /auth/me`.
- [x] Implementar notificaciones autenticadas, contador real, listado y marcado como leído.
- [x] Añadir estados de carga, vacío, error, reintento y prevención de envíos duplicados.
- [x] Centralizar Axios con `VITE_API_BASE_URL`; conservar tokens solo en memoria.
- [x] Implementar renovación coordinada de tokens, un único reintento y tratamiento separado de 403.
- [x] Limpiar sesión y desmontar datos del usuario al cerrar sesión.
- [x] Configurar Vite en `http://localhost:3000` con puerto estricto; no modificar CORS del backend.
- [x] Añadir generación reproducible de tipos TypeScript desde `app.openapi()`.
- [x] Revisar `.gitignore`: ya excluía `node_modules/`, `dist/`, `.vite/`, secretos y archivos de entorno; añadir caché de ESLint, exportación OpenAPI temporal y resultados de pruebas.

### Pendiente / limitaciones

- [ ] **Logout en el servidor:** no existe endpoint de cierre/revocación. «Cerrar sesión» elimina el acceso en esta página, pero no revoca tokens ya emitidos. Añadir un endpoint requiere aprobación independiente para el backend.
- [ ] **Búsqueda de registros médicos:** no existe endpoint global de búsqueda. La cabecera muestra «Búsqueda no disponible» sin simular resultados.
- [ ] Implementar las pantallas de perfil, citas, resultados, chat y teleconsulta cuando se aprueben por separado. La portada solo explica los servicios.
- [ ] Incorporar textos definitivos de condiciones de uso y política de privacidad. El backend exige `terms_accepted`; el diálogo recoge esa aceptación sin inventar documentos legales.
- [ ] Persistencia entre recargas: decisión pendiente de diseño de sesión. Actualmente se requiere iniciar sesión tras recargar y no se guardan tokens en localStorage, sessionStorage ni cookies.
- [ ] Paginación completa de notificaciones: el desplegable muestra como máximo las 50 más recientes e informa si existen más.
- [ ] Disponibilidad de notificaciones en tiempo real: el desplegable actualiza al abrir y mediante «Actualizar»; no se inventa un WebSocket de notificaciones.
- [ ] Verificar con una cuenta real y un backend local en ejecución. No se utilizan datos de pacientes ni credenciales reales en pruebas automatizadas.

### Verificación

- [x] Generación de tipos desde OpenAPI 3.1.0: 73 rutas, sin edición manual de los tipos generados.
- [x] TypeScript: `npm.cmd run typecheck`.
- [x] ESLint: `npm.cmd run lint`.
- [x] Pruebas del cliente HTTP: `npm.cmd test`, 8 comprobaciones aprobadas con un servidor local de fixtures. Incluyen renovación simultánea, 403, marcado como leído, errores/vacíos y logout durante renovación.
- [x] Compilación de producción: `npm.cmd run build`.
- [x] Navegador Chrome sin interfaz: escritorio de 1440 px y móvil de 375 px, sin desbordamiento horizontal, recursos locales con dimensiones SVG originales y sin excepciones de ejecución.
- [x] Comprobar en navegador el foco inicial y Escape del diálogo, registro profesional con aviso de aprobación, error/acceso correcto, lectura de notificaciones, vacío/error/reintento y limpieza local al cerrar sesión.
- [x] Revisar visualmente capturas de escritorio y móvil; guardadas en `frontend/test-results/` y excluidas de Git.

Las pruebas de interfaz usan fixtures exclusivamente en `frontend/tests/`. No equivalen a una prueba contra FastAPI con una cuenta real. No se han modificado routers, CORS, servicios ni modelos del backend.

### Endpoints de esta página

`POST /auth/login`, `POST /auth/register`, `POST /auth/refresh`, `GET /auth/me`, `GET /notifications/unread-count`, `GET /notifications`, `PATCH /notifications/{notification_id}/read`.

### Adaptaciones visuales acordadas

Se elimina el margen lateral vacío de 288 px del frame, se añade la marca ya existente, se apilan las columnas en móvil y se sustituyen las afirmaciones no verificadas por descripciones de funcionalidades reales. La fuente usa Inter si está instalada, con alternativas del sistema y sin peticiones a servicios externos de fuentes.
