import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import XStateLandingPage from './XStateLandingPage.jsx';

vi.mock('../../components/xstate-visualizer/XStateVisualizer', () => {
  return {
    XStateVisualizer: () => <div data-testid="xstate-visualizer" />,
  };
});

describe('XStateLandingPage', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetAllMocks();
  });

  it('does not crash when API returns nodes/edges as null', async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ nodes: null, edges: null }),
    });

    render(<XStateLandingPage />);

    expect(await screen.findByTestId('xstate-visualizer')).toBeInTheDocument();
  });

  it('renders an error message when workflow load fails', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    fetch.mockRejectedValue(new Error('Network error'));

    render(<XStateLandingPage />);

    expect(
      await screen.findByText(/Unable to load workflow data/i)
    ).toBeInTheDocument();

    consoleErrorSpy.mockRestore();
  });
});
