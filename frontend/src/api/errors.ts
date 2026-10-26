import axios from 'axios';

export function errorMessage(error: unknown): string {
  if (!axios.isAxiosError<unknown>(error)) return 'No se pudo completar la solicitud. Inténtalo de nuevo.';
  if (!error.response) return 'No se ha podido conectar con el servidor. Comprueba tu conexión e inténtalo de nuevo.';
  switch (error.response.status) {
    case 401: return 'La sesión ha caducado o las credenciales no son válidas. Inicia sesión de nuevo.';
    case 403: return 'Tu cuenta no tiene permiso para realizar esta acción.';
    case 404: return 'No se ha encontrado el recurso solicitado.';
    case 409: return 'El correo electrónico o el nombre de usuario ya está registrado.';
    case 422: return validationMessage(error.response.data);
    case 429: return 'Se han realizado demasiadas solicitudes. Espera un momento antes de volver a intentarlo.';
    default: return 'El servidor no ha podido completar la solicitud. Inténtalo de nuevo.';
  }
}

const fields: Record<string, string> = {
  name: 'nombre', dni: 'DNI/NIE', username: 'nombre de usuario', email: 'correo electrónico',
  password: 'contraseña', tel: 'teléfono', birth_date: 'fecha de nacimiento', role: 'tipo de cuenta',
  specialty: 'especialidad', bio: 'presentación', practice_address: 'dirección de consulta',
  practice_phone: 'teléfono de consulta', license_number: 'número de colegiación',
  default_consultation_duration_minutes: 'duración de consulta', terms_accepted: 'aceptación de condiciones',
};

function validationMessage(data: unknown): string {
  const base = 'Revisa los campos del formulario.';
  if (typeof data !== 'object' || data === null || !('detail' in data) || !Array.isArray(data.detail)) return base;
  const labels = data.detail.flatMap((item: unknown) => {
    if (typeof item !== 'object' || item === null || !('loc' in item) || !Array.isArray(item.loc)) return [];
    const field: unknown = item.loc.at(-1);
    return typeof field === 'string' && fields[field] ? [fields[field]] : [];
  });
  return labels.length ? `Revisa estos campos: ${[...new Set(labels)].join(', ')}.` : base;
}
