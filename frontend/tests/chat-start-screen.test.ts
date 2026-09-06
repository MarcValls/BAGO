import { describe, expect, it } from 'vitest';
import { shouldOpenStartScreen } from '../src/layout/chatStartScreen';

describe('shouldOpenStartScreen', () => {
  it('shows the welcome screen when there is nothing to resume', () => {
    expect(shouldOpenStartScreen({ startScreenRequested: true, isDocked: false, turnCount: 0 })).toBe(true);
  });

  it('does not interpose the welcome screen over an existing conversation', () => {
    expect(shouldOpenStartScreen({ startScreenRequested: true, isDocked: false, turnCount: 4 })).toBe(false);
  });

  it('never shows the welcome screen in the docked chat', () => {
    expect(shouldOpenStartScreen({ startScreenRequested: true, isDocked: true, turnCount: 0 })).toBe(false);
  });

  it('respects an explicit request to skip the welcome screen', () => {
    expect(shouldOpenStartScreen({ startScreenRequested: false, isDocked: false, turnCount: 0 })).toBe(false);
  });
});
