import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import hooks from 'eslint-plugin-react-hooks';

export default tseslint.config(
  { ignores: ['dist/**', 'test-results/**', 'src/types/api.generated.ts'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['src/**/*.{ts,tsx}'],
    plugins: { 'react-hooks': hooks },
    rules: { ...hooks.configs.recommended.rules },
  },
  {
    files: ['scripts/**/*.mjs', 'tests/**/*.mjs'],
    languageOptions: { globals: {
      process: 'readonly', console: 'readonly', URL: 'readonly', URLSearchParams: 'readonly',
      AbortController: 'readonly', setTimeout: 'readonly', clearTimeout: 'readonly',
      WebSocket: 'readonly', fetch: 'readonly', Buffer: 'readonly',
    } },
  },
);
