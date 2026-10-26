import type { components } from './api.generated';

export type User = components['schemas']['UserResponse'];
export type Tokens = components['schemas']['TokenResponse'];
export type Registration = components['schemas']['UserRegisterRequest'];
export type Notification = components['schemas']['NotificationResponse'];
export type NotificationPage = components['schemas']['NotificationListResponse'];
export type UnreadCount = components['schemas']['UnreadCountResponse'];
