import type { Tokens } from '../types/api';

// Memory only. A generation prevents an old request restoring a logged-out session.
let tokens: Tokens | null = null;
let generation = 0;
const listeners = new Set<() => void>();

export const session = {
  read: () => tokens,
  generation: () => generation,
  rotate(value: Tokens) {
    tokens = value;
  },
  replace(value: Tokens | null) {
    tokens = value;
    generation += 1;
    listeners.forEach((listener) => listener());
  },
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => { listeners.delete(listener); };
  },
};
