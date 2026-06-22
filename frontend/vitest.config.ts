import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    exclude: ['node_modules', 'tests/e2e/**'],
    css: { modules: { classNameStrategy: 'non-scoped' } },
  },
});
