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

const authenticated = {
  installed: true,
  authenticated: true,
  username: 'MarcValls',
  activeAccount: 'MarcValls',
  checkedAt: '2026-09-06T00:00:02Z',
};

const githubCliLoginArgs = [
  'auth',
  'login',
  '--hostname',
  'github.com',
  '--web',
  '--clipboard',
  '--git-protocol',
  'https',
  '--skip-ssh-key',
  '--scopes',
  'repo,workflow',
];

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

describe('GitHubAuthPanel', () => {
  afterEach(() => {
    delete window.bagoElectron;
  });

  it('detects a completed CLI authorization without a manual refresh', async () => {
    const runAuthorizedProcess = vi.fn().mockResolvedValue({ canceled: false, exit_code: 0, stderr: '' });
    const refresh = createDeferred<typeof authenticated>();
    window.bagoElectron = { runAuthorizedProcess };
    const client = {
      getGitHubAuthStatus: vi.fn().mockResolvedValue(unauthenticated),
      refreshGitHubAuth: vi.fn().mockReturnValue(refresh.promise),
    };

    render(<GitHubAuthPanel client={client as never} onClose={vi.fn()} />);
    const connect = await screen.findByRole('button', { name: /conectar con github/i });
    fireEvent.click(connect);

    expect(await screen.findByRole('status')).toHaveTextContent('detectará la sesión automáticamente');
    expect(connect).toHaveTextContent('Esperando autorización');
    expect(runAuthorizedProcess).toHaveBeenCalledWith('github_cli', githubCliLoginArgs);
    await waitFor(() => expect(client.refreshGitHubAuth).toHaveBeenCalledTimes(1));

    refresh.resolve(authenticated);

    expect(await screen.findByText('@MarcValls')).toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /conectar con github/i })).not.toBeInTheDocument();
  });

  it('uses an authenticated CLI session immediately', async () => {
    const client = {
      getGitHubAuthStatus: vi.fn().mockResolvedValue(authenticated),
      refreshGitHubAuth: vi.fn(),
    };

    render(<GitHubAuthPanel client={client as never} onClose={vi.fn()} />);

    expect(await screen.findByText('@MarcValls')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /refrescar estado/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cerrar sesión/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /conectar con github/i })).not.toBeInTheDocument();
    expect(client.refreshGitHubAuth).not.toHaveBeenCalled();
  });

  it('lets the user stop waiting without logging out or closing the panel', async () => {
    const onClose = vi.fn();
    const runAuthorizedProcess = vi.fn().mockResolvedValue({ canceled: false, exit_code: 0, stderr: '' });
    const refresh = createDeferred<typeof unauthenticated>();
    window.bagoElectron = { runAuthorizedProcess };
    const client = {
      getGitHubAuthStatus: vi.fn().mockResolvedValue(unauthenticated),
      refreshGitHubAuth: vi.fn().mockReturnValue(refresh.promise),
    };

    render(<GitHubAuthPanel client={client as never} onClose={onClose} />);
    fireEvent.click(await screen.findByRole('button', { name: /conectar con github/i }));

    expect(await screen.findByRole('button', { name: /dejar de esperar/i })).toBeInTheDocument();
    expect(runAuthorizedProcess).toHaveBeenCalledWith('github_cli', githubCliLoginArgs);
    await waitFor(() => expect(client.refreshGitHubAuth).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: /dejar de esperar/i }));
    refresh.resolve(unauthenticated);

    expect(await screen.findByRole('button', { name: /conectar con github/i })).toBeEnabled();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });
});
