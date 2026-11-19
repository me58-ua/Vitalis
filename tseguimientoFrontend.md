# Seguimiento del frontend

## Chat y solicitud de cita · 19/11/2026

- El menú y la pantalla de conversaciones del paciente muestran **Chat médico**. El menú, el acceso rápido y la pantalla de conversaciones del profesional muestran **Chat**.
- **Pedir cita** aparece en la barra lateral del paciente justo antes de **Mis citas**. Abre el directorio médico en `/patientPanel/equipoMedico`. **Mis citas → Reservar cita** también abre ese directorio.
- El directorio empieza con **Todas las modalidades** y muestra todos los profesionales activos. Las fichas de profesionales que han cerrado la admisión indican que no aceptan nuevos pacientes.
- Al elegir **Presencial**, el directorio muestra solo profesionales con al menos una franja semanal activa para citas presenciales. **Videoconsulta** muestra profesionales con una franja activa de vídeo y la videoconsulta habilitada. El filtro se aplica en `GET /professionals` mediante `appointment_type` antes de calcular el total y paginar. Cada cambio de modalidad vuelve a la primera página.
- Al reservar desde un resultado filtrado, el formulario abre con la modalidad elegida. Los horarios libres se consultan para la fecha y modalidad seleccionadas.

Consulta el [seguimiento anterior del frontend](seguimientoFrontend.md) para los detalles de la agenda y el flujo de reserva.
