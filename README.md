# Vitalis
App multiplataforma de salud con IA para detección temprana de riesgos, seguimiento de hábitos y teleconsulta con profesionales.

## Chat y vídeo

El chat usa la cita como sala (`appointment_id`). Tras reconectar un cliente WebSocket, debe recuperar mensajes perdidos con `GET /appointments/{appointment_id}/chat/messages?after_id=...`.

Para vídeo, el backend emite `domain`, `room_name`, `jwt` y `expires_at` desde `POST /appointments/{appointment_id}/video/join`. El frontend debe cargar `external_api.js` desde el dominio Jitsi y crear la sesión con `roomName` y `jwt`. Jitsi debe ejecutarse detrás de HTTPS; el navegador bloquea cámara y micrófono sin un contexto seguro, salvo `localhost`.

El stack Jitsi se inicia con el perfil opcional `video` y requiere `JITSI_DOMAIN`, `JITSI_APP_ID` y `JITSI_APP_SECRET` en `backend/.env`. El secreto Jitsi es independiente del secreto JWT de la API.
