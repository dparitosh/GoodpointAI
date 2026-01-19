// Vitest is configured with `globals: true` in vitest.config.js.
// Using globals here avoids a Vitest 4.x edge-case where importing `it`
// can fail with "failed to find the current suite".

it('sanity works', () => {
  expect(1 + 1).toBe(2);
});
