import type { components } from './api.generated';

export type User = components['schemas']['UserResponse'];
export type Tokens = components['schemas']['TokenResponse'];
export type Registration = components['schemas']['UserRegisterRequest'];
export type Notification = components['schemas']['NotificationResponse'];
export type NotificationPage = components['schemas']['NotificationListResponse'];
export type UnreadCount = components['schemas']['UnreadCountResponse'];
export type AdminUserPage = components['schemas']['AdminUserListResponse'];
export type AuditPage = components['schemas']['AuditLogListResponse'];
export type AuditQuery = NonNullable<import('./api.generated').operations['list_audit_logs_admin_audit_logs_get']['parameters']['query']>;
export type AppointmentSummary = components['schemas']['AdminAppointmentSummary'];
export type AppointmentList = components['schemas']['AdminAppointmentListResponse'];
export type UpcomingAppointments = components['schemas']['AdminUpcomingAppointmentsResponse'];
export type CreateAppointment = components['schemas']['AdminAppointmentCreate'];
export type UpdateAppointment = components['schemas']['AdminAppointmentUpdate'];
export type AppointmentQuery = NonNullable<import('./api.generated').operations['list_admin_appointments_admin_appointments_get']['parameters']['query']>;
export type AdminMonthlyMetrics = components['schemas']['AdminMonthlyMetricsResponse'];
export type MonthlyMetric = components['schemas']['MonthlyMetric'];
