# Frontend de Vitalis

Portada pública basada en Figma `15:166`, con diálogos de autenticación y notificaciones. El seguimiento por página está en [`../seguimientoFrontend.md`](../seguimientoFrontend.md).

## Desarrollo

Desde `frontend/`:

```powershell
npm.cmd ci
Copy-Item .env.example .env.local
npm.cmd run dev
```

Abrir **http://localhost:3000**. El puerto es estricto porque esa es la única procedencia permitida por el CORS actual. No usar `127.0.0.1:3000` ni `localhost:5173` sin acordar cambios de CORS. Configurar `VITE_API_BASE_URL` en `.env.local` con la URL del backend; el ejemplo usa `http://localhost:8000`. Reiniciar Vite al cambiar variables. El backend se inicia por separado con su configuración habitual.

Las variables `VITE_*` son públicas: no introducir secretos. El cliente envía Bearer tokens, no cookies de autenticación. Los tokens solo viven en memoria; recargar cierra la sesión local. «Cerrar todas las sesiones» llama a `POST /auth/logout`: revoca todos los access/refresh tokens previos de la cuenta mediante `session_version`. Si el servidor falla, se muestra un error y se permite reintentar; no se simula un cierre satisfactorio.

## Contrato y tipos

```powershell
npm.cmd run api:types
```

El script usa `backend/venv/Scripts/python.exe` en Windows o `backend/venv/bin/python` en otros sistemas. Se puede establecer `VITALIS_PYTHON` con otro intérprete. Requiere las dependencias y la configuración habituales del backend. Importa `app.main` para exportar `app.openapi()`; no inicia el lifespan ni consulta la base de datos. No imprime errores de configuración que puedan contener secretos.

`src/types/api.generated.ts` se genera y se versiona; **no editar a mano**. `openapi.json` es una exportación temporal ignorada. `src/types/api.ts` solo expone alias a los tipos generados. Axios es el único transporte REST. Los tipos estáticos no validan respuestas en ejecución.

## Comprobaciones

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
npm.cmd run test:browser
```

Las pruebas HTTP usan únicamente fixtures dentro de `tests/`, nunca como fallback de la aplicación. Las verificaciones de navegador utilizan el navegador Chrome instalado y no requieren otra biblioteca. Los resultados y capturas locales se guardan en `test-results/` (ignorado).

## Probar con una cuenta real

1. Iniciar el backend con su configuración local y arrancar Vite como se indica arriba.
2. Abrir `http://localhost:3000` y pulsar «Iniciar sesión»; introducir una cuenta real propia, sin compartir credenciales en el código o en el chat.
3. Confirmar que aparece el nombre real y que la campana muestra los datos del servidor. Si no existen notificaciones debe verse el estado vacío.
4. Abrir el desplegable y marcar una notificación como leída; comprobar el contador actualizado.
5. Probar credenciales incorrectas, desconexión del backend y «Reintentar». Un 403 no debe convertirse en una renovación de sesión.
6. Abrir «Buscar documentos médicos», buscar una descripción o tipo (`informe`, `analitica`, `otro`) y descargar un resultado. Se admiten filtros por tipo y paginación. Solo se consultan documentos permitidos para la cuenta; no se busca dentro de PDFs o imágenes. Un usuario sin documentos verá un estado vacío.
7. Pulsar «Cerrar todas las sesiones» y comprobar que desaparecen nombre, documentos y notificaciones. Los access/refresh tokens anteriores deben quedar invalidados en el backend. Recargar solo elimina el acceso local, no sustituye al logout del servidor.
8. Si se prueba el registro, hacerlo solo en un entorno de desarrollo autorizado. Las cuentas profesionales necesitan aprobación del administrador.
9. Revisar a 375 px de ancho, navegar con Tab, abrir/cerrar diálogos con Escape y comprobar que no hay desbordamiento horizontal.

No se afirma que exista integración validada con usuarios reales hasta realizar estos pasos. La búsqueda se limita a documentos; la reserva, las consultas y la búsqueda dentro del contenido de archivos pertenecen a tareas futuras. El contrato ampliado está documentado en `../backend/docs/homepage-contract.md`.


## LoginPage y destinos por rol

La ruta `/login` implementa el frame Figma `15:2`, adaptado al contrato real. Envía formulario URL-encoded a `POST /auth/login` y obtiene la cuenta mediante `GET /auth/me`. Se conservan Axios, los tipos OpenAPI y los tokens en memoria existentes; no se añaden dependencias ni cambios de backend.

Después del acceso, `patient` navega a `/patientPanel` («Página de paciente») y `professional` a `/professionalDashboard` («Página de profesional»). Son pantallas provisionales sin datos clínicos. `admin` vuelve a `/`. Las rutas de panel requieren sesión y el rol correspondiente. Recargar elimina la sesión local y vuelve a `/login`.

Para probar: iniciar backend y Vite, abrir `http://localhost:3000/login` e introducir una cuenta real de paciente; comprobar `/patientPanel`. Cerrar todas las sesiones y repetir con un profesional activo/aprobado; comprobar `/professionalDashboard`. Probar credenciales incorrectas, campos vacíos, mostrar/ocultar contraseña, backend desconectado y anchos de 375 y 1280 px. Intentar el panel del otro rol y recargar para comprobar las redirecciones.

Los registros siguen disponibles desde la portada. La recuperación completa de contraseña aún no tiene pantalla; LoginPage informa de ello. No se muestran acceso social, recuerdo de dispositivo ni afirmaciones de certificación o precisión clínica. Las pruebas de navegador usan fixtures sintéticos y no acreditan integración con cuentas reales.
