import axios from 'axios';
import { apiConfigured } from './client';

export interface UserFormErrors { summary: string; fields: Record<string, string> }
export const userFieldLabels: Record<string, string> = {
  name: 'Nombre completo', dni: 'DNI / NIE', username: 'Nombre de usuario', email: 'Correo electrónico',
  tel: 'Teléfono', password: 'Contraseña', birth_date: 'Fecha de nacimiento', gender: 'Género', role: 'Tipo de cuenta',
  address: 'Dirección', blood_type: 'Grupo sanguíneo', timezone: 'Zona horaria', sex_at_birth: 'Sexo al nacer',
  height_cm: 'Altura', weight_kg: 'Peso', specialty: 'Especialidad', license_number: 'Número de colegiación',
  bio: 'Presentación profesional', practice_address: 'Dirección de consulta', practice_phone: 'Teléfono de consulta',
  default_consultation_duration_minutes: 'Duración de consulta', professional_profile: 'Perfil profesional', patient_profile: 'Perfil de paciente',
  search: 'Búsqueda', page: 'Página', page_size: 'Usuarios por página', is_active: 'Estado de la cuenta',
};
const codes: Record<string, string> = {
  PROFILE_CHANGE_STALE: 'Esta solicitud ya fue revisada o reemplazada. Cierra la ventana y actualiza la lista antes de revisarla.',
  PROFILE_CHANGE_IDENTIFIER_CONFLICT: 'El número de colegiación ya está en uso. La solicitud sigue pendiente; recházala indicando el motivo o pide su corrección.',
  PROFILE_CHANGE_REASON_REQUIRED: 'Indica el motivo del rechazo.',
  DUPLICATE_EMAIL: 'Este correo electrónico ya está registrado. Utiliza otro.',
  DUPLICATE_USERNAME: 'Este nombre de usuario ya está registrado. Elige otro.',
  DUPLICATE_DNI: 'Este DNI / NIE ya está registrado. Revisa si la cuenta ya existe.',
  DUPLICATE_LICENSE_NUMBER: 'Este número de colegiación ya está registrado. Revisa el perfil profesional.',
  USER_IDENTIFIER_CONFLICT: 'El DNI / NIE, correo, nombre de usuario o número de colegiación ya está registrado. Revisa esos campos.',
  PROFESSIONAL_PROFILE_REQUIRED: 'Completa el perfil profesional: la especialidad y el número de colegiación son obligatorios.',
  PROFILE_ROLE_MISMATCH: 'El perfil no corresponde al tipo de cuenta seleccionado. Revisa el tipo de cuenta.',
  PROFESSIONAL_APPROVAL_REQUIRED: 'El profesional necesita aprobación antes de activar su cuenta. Abre su perfil y utiliza «Aprobar profesional».',
  REQUIRED_FIELD_NULL: 'Los datos obligatorios no pueden quedar vacíos. Revisa el formulario.',
  INVALID_TIMEZONE: 'Selecciona una zona horaria válida, por ejemplo Europe/Madrid.',
  ROLE_REQUIRED: 'Selecciona un tipo de cuenta válido: paciente, profesional o administrador.',
};
function record(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null; }

export function adminUserError(error: unknown, action: 'load' | 'save' | 'delete' | 'approve' = 'load'): UserFormErrors {
  const fields: Record<string, string> = {};
  const result = (summary: string) => ({ summary, fields });
  if (!apiConfigured) return result('No se ha configurado la conexión con el servidor. Configura VITE_API_BASE_URL y reinicia la aplicación.');
  if (!axios.isAxiosError<unknown>(error)) return result('No se pudo completar la operación. Vuelve a intentarlo.');
  if (!error.response) return result(error.code === 'ECONNABORTED'
    ? 'El servidor ha tardado demasiado en responder. Comprueba el resultado antes de volver a guardar.'
    : 'No se ha podido conectar con el servidor. Comprueba tu conexión. Si estabas guardando, actualiza la lista antes de repetir la operación.');
  const status = error.response.status;
  const body = error.response.data;
  const detail: unknown = record(body) ? body.detail : undefined;
  if (status === 401) return result('Tu sesión ha caducado o la cuenta está inactiva. Inicia sesión de nuevo para continuar.');
  if (status === 403) return result('No tienes permiso para gestionar usuarios. Esta operación requiere una cuenta de administrador.');
  if (status === 404) return result('La cuenta o el perfil ya no existe. Cierra esta ventana y actualiza la lista.');
  if (status === 409) {
    if (action === 'delete') return result('No se puede eliminar esta cuenta porque tiene registros relacionados. Puedes desactivarla para impedir el acceso.');
    if (typeof detail === 'string' && codes[detail]) {
      const key = detail.replace('DUPLICATE_', '').toLowerCase();
      if (detail.startsWith('DUPLICATE_')) fields[key] = codes[detail];
      return result(codes[detail]);
    }
    return result(codes.USER_IDENTIFIER_CONFLICT ?? 'Hay datos de identificación duplicados. Revisa el formulario.');
  }
  if (status === 422 || status === 400) {
    if (typeof detail === 'string') return result(codes[detail] || 'Los datos no son válidos. Revisa los campos e inténtalo de nuevo.');
    if (Array.isArray(detail)) for (const item of detail) {
      if (!record(item)) continue;
      const location = Array.isArray(item.loc) ? item.loc : [];
      const key = location.at(-1);
      const message = typeof item.msg === 'string' ? item.msg : '';
      const code = Object.keys(codes).find(code => message.includes(code));
      const label = typeof key === 'string' ? userFieldLabels[key] : undefined;
      let translated = (code ? codes[code] : undefined) ?? `${label || 'Campo'}: el valor no es válido.`;
      const ctx = record(item.ctx) ? item.ctx : {};
      if (!code) switch (item.type) {
        case 'missing': translated = `${label || 'Campo'}: este dato es obligatorio.`; break;
        case 'string_too_short': translated = `${label}: introduce al menos ${ctx.min_length} caracteres.`; break;
        case 'string_too_long': translated = `${label}: introduce como máximo ${ctx.max_length} caracteres.`; break;
        case 'greater_than_equal': translated = `${label}: el valor mínimo es ${ctx.ge}.`; break;
        case 'less_than_equal': translated = `${label}: el valor máximo es ${ctx.le}.`; break;
        case 'greater_than': translated = `${label}: introduce un valor mayor que ${ctx.gt}.`; break;
        case 'date_from_datetime_parsing': case 'date_parsing': translated = 'Fecha de nacimiento: introduce una fecha válida.'; break;
        case 'int_parsing': case 'int_from_float': translated = `${label}: introduce un número entero válido.`; break;
        case 'finite_number': case 'float_parsing': translated = `${label}: introduce un número válido.`; break;
        case 'enum': translated = 'Selecciona un tipo de cuenta válido.'; break;
        case 'value_error':
          if (key === 'username') translated = 'Nombre de usuario: utiliza letras, números, guiones o guiones bajos.';
          else if (key === 'email') translated = 'Correo electrónico: introduce una dirección válida.';
          else translated = `${label || 'Campo'}: introduce un valor válido que no esté vacío.`;
      }
      if (typeof key === 'string' && key !== 'body') fields[key] = translated;
      else fields._form = translated;
    }
    return result('No se ha guardado. Revisa los campos indicados e inténtalo de nuevo.');
  }
  if (status === 429) return result('Has realizado demasiadas solicitudes. Espera un momento antes de volver a intentarlo.');
  if (status >= 500) return result('El servidor no ha podido completar la operación. Inténtalo de nuevo más tarde. Si estabas guardando, actualiza la lista antes de repetirla.');
  return result('No se pudo completar la operación. Actualiza la lista e inténtalo de nuevo.');
}
