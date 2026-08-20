// @vitest-environment happy-dom
import { describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { GlobalHeader } from '../src/layout/GlobalHeader';

const baseProps = {
  snapshot: null,
  workspaceHint: '',
  apiBase: 'http://127.0.0.1:8080',
  apiToken: '',
  activeSection: 'home' as const,
  busy: false,
  onApiConfigChange: vi.fn(),
  onOpenPalette: vi.fn(),
  onToggleSidebar: vi.fn(),
  onRefresh: vi.fn(),
  onSetMode: vi.fn(),
  onSetAppearanceTheme: vi.fn(),
  onRunCommand: vi.fn(),
  onChooseWorkspace: vi.fn(),
  onGoHome: vi.fn(),
  onOpenHelp: vi.fn(),
  onToggleChatDock: vi.fn(),
  chatDocked: false,
  globalMode: 'normal' as const,
  appearanceTheme: 'dark' as const,
  sidebarCollapsed: true,
};

describe('GlobalHeader', () => {
  it('renders the chat dock toggle with the undocked label', () => {
    const { container } = render(<GlobalHeader {...baseProps} chatDocked={false} />);
    const button = container.querySelector('.chat-dock-toggle');
    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute('aria-pressed', 'false');
    expect(button).toHaveAttribute('title', 'Acoplar chat a esta pantalla (Ctrl+Shift+C)');
  });

  it('marks the chat dock toggle as active when docked', () => {
    const { container } = render(<GlobalHeader {...baseProps} chatDocked={true} />);
    const button = container.querySelector('.chat-dock-toggle');
    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute('aria-pressed', 'true');
    expect(button).toHaveClass('is-active');
    expect(button).toHaveAttribute('title', 'Quitar chat acoplado (Ctrl+Shift+C)');
  });
});
