// @vitest-environment happy-dom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GitHubAuthPanel } from '../src/features/github/GitHubAuthPanel';

const unauthenticated = {
  installed: true,
  authenticated: false,
  checkedAt: '2026-09-06T00:00:00Z',
};

describe('GitHubAuthPanel', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('detects a completed CLI authorization without a manual refresh', async () => {
    const client = {
      getGitHubAuthStatus: vi.fn().mockResolvedValue(unauthenticated),
      startGitHubAuth: vi.fn().mockResolvedValue({ pending: true, installed: true }),
      refreshGitHubAuth: vi.fn().mockResolvedValue({
        installed: true,
        authenticated: true,
        username: 'MarcValls',
        activeAccount: 'MarcValls',
        checkedAt: '2026-09-06T00:00:02Z',
      }),
      logoutGitHub: vi.fn(),
    };

    render(<GitHubAuthPanel client={client as never} onClose={vi.fn()} />);
    const connect = await screen.findByRole('button', { name: /conectar con github/i });
    fireEvent.click(connect);

    expect(await screen.findByRole('status')).toHaveTextContent('detectará la sesión automáticamente');
    expect(connect).toHaveTextContent('Esperando autorización');

    await waitFor(() => expect(client.refreshGitHubAuth).toHaveBeenCalledOnce(), { timeout: 3_000 });
    expect(await screen.findByText('@MarcValls')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /conectar con github/i })).not.toBeInTheDocument();
  });

  it('uses an authenticated CLI session immediately', async () => {
    const client = {
      getGitHubAuthStatus: vi.fn()
        .mockResolvedValueOnce(unauthenticated)
        .mockResolvedValueOnce({ ...unauthenticated, authenticated: true, username: 'MarcValls' }),
      startGitHubAuth: vi.fn().mockResolvedValue({ authenticated: true }),
      refreshGitHubAuth: vi.fn(),
      logoutGitHub: vi.fn(),
    };

    render(<GitHubAuthPanel client={client as never} onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: /conectar con github/i }));

    expect(await screen.findByText('@MarcValls')).toBeInTheDocument();
    expect(client.refreshGitHubAuth).not.toHaveBeenCalled();
  });

  it('lets the user stop waiting without logging out or closing the panel', async () => {
    const client = {
      getGitHubAuthStatus: vi.fn().mockResolvedValue(unauthenticated),
      startGitHubAuth: vi.fn().mockResolvedValue({ pending: true, installed: true }),
      refreshGitHubAuth: vi.fn().mockResolvedValue(unauthenticated),
      logoutGitHub: vi.fn(),
    };

    render(<GitHubAuthPanel client={client as never} onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: /conectar con github/i }));
    fireEvent.click(await screen.findByRole('button', { name: /dejar de esperar/i }));

    expect(await screen.findByRole('button', { name: /conectar con github/i })).toBeEnabled();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
