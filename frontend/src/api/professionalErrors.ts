import axios from 'axios';
import { errorMessage } from './errors';

export function professionalError(error: unknown): string {
  if (!axios.isAxiosError<unknown>(error)) return errorMessage(error);
  const status = error.response?.status;
  const body = error.response?.data;
  const detail = typeof body === 'object' && body !== null && 'detail' in body ? body.detail : undefined;
  if (detail === 'OUTSIDE_WORKING_HOURS') return 'La cita queda fuera del horario de citas del profesional. Configura una franja en Agenda o elige otra hora.';
  if (detail === 'SCHEDULE_OVERLAP') return 'Esta franja se solapa con otro horario activo del mismo canal y día. Revisa las horas o desactiva la otra franja.';
  if (detail === 'SCHEDULE_GROUP_CHANGED') return 'Los horarios de este grupo han cambiado. Actualiza los horarios antes de volver a guardarlos.';
  if (detail === 'SCHEDULE_INVALID_RANGE_OR_SLOT') return 'Revisa el intervalo y la duración: el fin debe ser posterior al inicio y debe caber al menos una cita completa.';
  if (detail === 'TIME_BLOCK_CONFLICT') return 'El intervalo coincide con una cita existente o con otro bloqueo. Reprograma o cancela la cita antes de bloquear; no se cancelará automáticamente.';
  if (detail === 'PROFILE_CHANGE_EMPTY') return 'No has cambiado ningún dato del perfil vigente.';
  if (detail === 'PROFESSIONAL_APPROVAL_REQUIRED') return 'El perfil debe estar aprobado antes de solicitar cambios.';
  if (status === 403) return 'No tienes permiso para realizar esta acción. Comprueba que accedes con la cuenta profesional y que el paciente o la cita te corresponden.';
  if (status === 404) return 'No se ha encontrado la cita, el paciente o el perfil solicitado. Actualiza los datos e inténtalo de nuevo.';
  if (status === 409) return 'No se pudo guardar: el horario entra en conflicto con otra reserva o un bloqueo, o los datos han cambiado. Revisa la agenda y vuelve a intentarlo.';
  return errorMessage(error);
}
