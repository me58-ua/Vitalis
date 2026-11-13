# Vitalis
App multiplataforma de salud con IA para detección temprana de riesgos, seguimiento de hábitos y teleconsulta con profesionales.

## Recetas del paciente

`/patientPanel/misRecetas` muestra un documento por cita, con el título, el tipo (medicación, solicitud de prueba/procedimiento u otro), el profesional, la cita y las fechas introducidas por el profesional. La dosis y las instrucciones permanecen en el PDF o imagen original. El formulario exige título, tipo y fecha de emisión; la caducidad y el código del documento son opcionales. Sustituir un archivo actualiza el mismo registro y sus metadatos, conservando los permisos y el plazo de emisión existentes.

La migración `0034_prescription_metadata` añade campos opcionales a los registros existentes sin inventar fechas. Para una instalación pendiente de actualizar, ejecuta `venv\Scripts\alembic.exe upgrade head` desde `backend`. Las recetas sin fecha de caducidad muestran «Vigencia no indicada». La vigencia se calcula por días naturales en la zona horaria del paciente; se avisa desde siete días antes y durante todo el día de caducidad. Este aviso se muestra en la página y no envía correos ni notificaciones programadas.

## Sesiones y demostración con varias cuentas

La sesión se conserva al recargar la página mediante `sessionStorage`, que mantiene el almacenamiento separado por pestaña. El frontend verifica la sesión con `GET /auth/me` antes de mostrar páginas protegidas y renueva los tokens mediante `POST /auth/refresh` cuando el token de acceso ha caducado. Si la conexión falla durante la restauración, muestra un mensaje en español y permite reintentar o volver a iniciar sesión.

`POST /auth/logout` revoca únicamente la sesión de inicio de sesión actual, incluidos sus tokens de acceso y actualización. No cierra otras sesiones iniciadas de forma independiente, ni de la misma cuenta ni de otras cuentas. Los textos de cierre de sesión reflejan este comportamiento. Un restablecimiento de contraseña sigue invalidando las sesiones de la cuenta.


## Chat y vídeo

El chat usa la cita como sala (`appointment_id`). Tras reconectar un cliente WebSocket, debe recuperar mensajes perdidos con `GET /appointments/{appointment_id}/chat/messages?after_id=...`.

Para vídeo, el backend emite `domain`, `room_name`, `jwt` y `expires_at` desde `POST /appointments/{appointment_id}/video/join`. El frontend debe cargar `external_api.js` desde el dominio Jitsi y crear la sesión con `roomName` y `jwt`. Jitsi debe ejecutarse detrás de HTTPS; el navegador bloquea cámara y micrófono sin un contexto seguro, salvo `localhost`.

El stack Jitsi se inicia con el perfil opcional `video` y requiere `JITSI_DOMAIN` (dominio público, por ejemplo `localhost:8443`), `JITSI_XMPP_DOMAIN` (por ejemplo `meet.jitsi`), `JITSI_APP_ID`, `JITSI_APP_SECRET`, `JICOFO_AUTH_PASSWORD` y `JVB_AUTH_PASSWORD` en `backend/.env`. El secreto Jitsi es independiente del secreto JWT de la API. El claim `sub` del JWT usa `JITSI_XMPP_DOMAIN`; `JITSI_DOMAIN` solo se devuelve al frontend para cargar `external_api.js`.
