// @vitest-environment happy-dom
import { describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom';
import { fireEvent, render } from '@testing-library/react';
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
  onOpenChat: vi.fn(),
  chatDocked: false,
  globalMode: 'normal' as const,
  appearanceTheme: 'dark' as const,
  sidebarCollapsed: true,
};

describe('GlobalHeader', () => {
  it('opens the full-screen chat directly from the top bar', () => {
    const onOpenChat = vi.fn();
    const { container } = render(<GlobalHeader {...baseProps} onOpenChat={onOpenChat} chatDocked={false} />);
    const button = container.querySelector('.chat-open-button');
    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute('aria-label', 'Abrir chat');
    expect(button).toHaveAttribute('title', 'Abrir chat a pantalla completa');

    fireEvent.click(button as HTMLElement);
    expect(onOpenChat).toHaveBeenCalledOnce();
  });

  it('keeps the dock indicator while the chat is docked', () => {
    const { container } = render(<GlobalHeader {...baseProps} chatDocked={true} />);
    const button = container.querySelector('.chat-open-button');
    expect(button).toBeInTheDocument();
    expect(button).toHaveClass('is-active');
    expect(button).toHaveAttribute('title', 'Abrir chat a pantalla completa');
  });
});
