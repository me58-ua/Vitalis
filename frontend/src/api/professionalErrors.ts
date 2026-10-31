import axios from 'axios';
import { errorMessage } from './errors';

export function professionalError(error: unknown): string {
  if (!axios.isAxiosError<unknown>(error)) return errorMessage(error);
  const status = error.response?.status;
  if (status === 403) return 'No tienes permiso para realizar esta acción. Comprueba que accedes con la cuenta profesional y que el paciente o la cita te corresponden.';
  if (status === 404) return 'No se ha encontrado la cita, el paciente o el perfil solicitado. Actualiza los datos e inténtalo de nuevo.';
  if (status === 409) return 'No se pudo guardar la cita: el horario entra en conflicto con otra reserva o los datos han cambiado. Revisa la agenda y vuelve a intentarlo.';
  return errorMessage(error);
}
