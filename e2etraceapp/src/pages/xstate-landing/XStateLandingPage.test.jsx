import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

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

  it('renders with the sample demo flow when no workflows are returned', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ([]),
    });

    render(
      <MemoryRouter>
        <XStateLandingPage />
      </MemoryRouter>
    );

    expect(await screen.findByLabelText(/Workflow selector/i)).toBeInTheDocument();
    expect(await screen.findByTestId('xstate-visualizer')).toBeInTheDocument();
  });

  it('loads and renders the first workflow graph when workflows exist', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ([{ id: 'wf-1', name: 'WF One' }]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ workflow_config: { nodes: null, edges: null } }),
      });

    render(
      <MemoryRouter>
        <XStateLandingPage />
      </MemoryRouter>
    );

    expect(await screen.findByTestId('xstate-visualizer')).toBeInTheDocument();
  });
});
