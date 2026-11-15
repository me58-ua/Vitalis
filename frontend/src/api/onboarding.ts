import axios from 'axios';
import { api } from './client';
import { errorMessage } from './errors';
import type { components } from '../types/api.generated';

export type OnboardingState = components['schemas']['OnboardingChatState'];
export type OnboardingReview = components['schemas']['ChatReview'];

export async function getOnboarding(signal: AbortSignal) {
  return (await api.get<OnboardingState>('/onboarding/chat', { signal })).data;
}
export async function giveOnboardingConsent(accepted: boolean, signal: AbortSignal) {
  return (await api.post<OnboardingState>('/onboarding/chat/consent', { accepted }, { signal })).data;
}
export async function answerOnboarding(question_id: string, message: string, signal: AbortSignal) {
  return (await api.post<OnboardingState>('/onboarding/chat/answer', { question_id, message }, { signal, timeout: 70000 })).data;
}
export async function confirmOnboarding(draft_id: string, confirmed: boolean, signal: AbortSignal) {
  return (await api.post<OnboardingState>('/onboarding/chat/confirm', { draft_id, confirmed }, { signal })).data;
}
export function onboardingError(error: unknown) {
  if (axios.isAxiosError<{ detail?: unknown }>(error) && typeof error.response?.data.detail === 'string') return error.response.data.detail;
  return errorMessage(error);
}
